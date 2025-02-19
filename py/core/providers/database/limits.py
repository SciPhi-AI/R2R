import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from core.base import Handler
from shared.abstractions import User

from ...base.providers.database import DatabaseConfig, LimitSettings
from .base import PostgresConnectionManager

logger = logging.getLogger(__name__)


class PostgresLimitsHandler(Handler):
    TABLE_NAME = "request_log"

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        config: DatabaseConfig,
    ):
        """
        :param config: The global DatabaseConfig with default rate limits.
        """
        super().__init__(project_name, connection_manager)
        self.config = config

        logger.debug(
            f"Initialized PostgresLimitsHandler with project: {project_name}"
        )

    async def create_tables(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)} (
            time TIMESTAMPTZ NOT NULL,
            user_id UUID NOT NULL,
            route TEXT NOT NULL
        );
        """
        logger.debug("Creating request_log table if not exists")
        await self.connection_manager.execute_query(query)

    async def _count_requests(
        self,
        user_id: UUID,
        route: Optional[str],
        since: datetime,
    ) -> int:
        """Count how many requests a user (optionally for a specific route) has
        made since the given datetime."""
        if route:
            query = f"""
            SELECT COUNT(*)::int
            FROM {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
            WHERE user_id = $1
              AND route = $2
              AND time >= $3
            """
            params = [user_id, route, since]
            logger.debug(
                f"Counting requests for user={user_id}, route={route}"
            )
        else:
            query = f"""
            SELECT COUNT(*)::int
            FROM {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
            WHERE user_id = $1
              AND time >= $2
            """
            params = [user_id, since]
            logger.debug(f"Counting all requests for user={user_id}")

        result = await self.connection_manager.fetchrow_query(query, params)
        return result["count"] if result else 0

    async def _count_monthly_requests(
        self,
        user_id: UUID,
        route: Optional[str] = None,  # <--- ADDED THIS
    ) -> int:
        """Count the number of requests so far this month for a given user.

        If route is provided, count only for that route. Otherwise, count
        globally.
        """
        now = datetime.now(timezone.utc)
        start_of_month = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        return await self._count_requests(
            user_id, route=route, since=start_of_month
        )

    def determine_effective_limits(
        self, user: User, route: str
    ) -> LimitSettings:
        """
        Determine the final effective limits for a user+route combination,
        respecting:
          1) Global defaults
          2) Route-specific overrides
          3) User-level overrides
        """
        # ------------------------
        # 1) Start with global/base
        # ------------------------
        base_limits = self.config.limits

        # We’ll make a copy so we don’t mutate self.config.limits directly
        effective = LimitSettings(
            global_per_min=base_limits.global_per_min,
            route_per_min=base_limits.route_per_min,
            monthly_limit=base_limits.monthly_limit,
        )

        # ------------------------
        # 2) Route-level overrides
        # ------------------------
        route_config = self.config.route_limits.get(route)
        if route_config:
            if route_config.global_per_min is not None:
                effective.global_per_min = route_config.global_per_min
            if route_config.route_per_min is not None:
                effective.route_per_min = route_config.route_per_min
            if route_config.monthly_limit is not None:
                effective.monthly_limit = route_config.monthly_limit

        # ------------------------
        # 3) User-level overrides
        # ------------------------
        # The user object might have a dictionary of overrides
        # which can include route_overrides, global_per_min, monthly_limit, etc.
        user_overrides = user.limits_overrides or {}

        # (a) "global" user overrides
        if user_overrides.get("global_per_min") is not None:
            effective.global_per_min = user_overrides["global_per_min"]
        if user_overrides.get("monthly_limit") is not None:
            effective.monthly_limit = user_overrides["monthly_limit"]

        # (b) route-level user overrides
        route_overrides = user_overrides.get("route_overrides", {})
        specific_config = route_overrides.get(route, {})
        if specific_config.get("global_per_min") is not None:
            effective.global_per_min = specific_config["global_per_min"]
        if specific_config.get("route_per_min") is not None:
            effective.route_per_min = specific_config["route_per_min"]
        if specific_config.get("monthly_limit") is not None:
            effective.monthly_limit = specific_config["monthly_limit"]

        return effective

    async def check_limits(self, user: User, route: str):
        """Perform rate limit checks for a user on a specific route.

        :param user: The fully-fetched User object with .limits_overrides, etc.
        :param route: The route/path being accessed.
        :raises ValueError: if any limit is exceeded.
        """
        user_id = user.id
        now = datetime.now(timezone.utc)
        one_min_ago = now - timedelta(minutes=1)

        # 1) Compute the final (effective) limits for this user & route
        limits = self.determine_effective_limits(user, route)

        # 2) Check each of them in turn, if they exist
        # ------------------------------------------------------------
        # Global per-minute limit
        # ------------------------------------------------------------
        if limits.global_per_min is not None:
            user_req_count = await self._count_requests(
                user_id, None, one_min_ago
            )
            if user_req_count > limits.global_per_min:
                logger.warning(
                    f"Global per-minute limit exceeded for "
                    f"user_id={user_id}, route={route}"
                )
                raise ValueError("Global per-minute rate limit exceeded")

        # ------------------------------------------------------------
        # Route-specific per-minute limit
        # ------------------------------------------------------------
        if limits.route_per_min is not None:
            route_req_count = await self._count_requests(
                user_id, route, one_min_ago
            )
            if route_req_count > limits.route_per_min:
                logger.warning(
                    f"Per-route per-minute limit exceeded for "
                    f"user_id={user_id}, route={route}"
                )
                raise ValueError("Per-route per-minute rate limit exceeded")

        # ------------------------------------------------------------
        # Monthly limit
        # ------------------------------------------------------------
        if limits.monthly_limit is not None:
            # If you truly want a per-route monthly limit, we pass 'route'.
            # If you want a global monthly limit, pass 'None'.
            monthly_count = await self._count_monthly_requests(user_id, route)
            if monthly_count > limits.monthly_limit:
                logger.warning(
                    f"Monthly limit exceeded for user_id={user_id}, "
                    f"route={route}"
                )
                raise ValueError("Monthly rate limit exceeded")

    async def log_request(self, user_id: UUID, route: str):
        """Log a successful request to the request_log table."""
        query = f"""
        INSERT INTO {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
        (time, user_id, route)
        VALUES (CURRENT_TIMESTAMP AT TIME ZONE 'UTC', $1, $2)
        """
        await self.connection_manager.execute_query(query, [user_id, route])


# import logging
# from datetime import datetime, timedelta, timezone
# from typing import Optional
# from uuid import UUID

# from core.base import Handler
# from shared.abstractions import User

# from ..base.providers.database import DatabaseConfig, LimitSettings
# from .base import PostgresConnectionManager

# logger = logging.getLogger(__name__)

# class PostgresLimitsHandler(Handler):
#     TABLE_NAME = "request_log"

#     def __init__(
#         self,
#         project_name: str,
#         connection_manager: PostgresConnectionManager,
#         config: DatabaseConfig,
#     ):
#         """
#         :param config: The global DatabaseConfig with default rate limits.
#         """
#         super().__init__(project_name, connection_manager)
#         self.config = config

#         logger.debug(
#             f"Initialized PostgresLimitsHandler with project: {project_name}"
#         )

#     async def create_tables(self):
#         query = f"""
#         CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)} (
#             time TIMESTAMPTZ NOT NULL,
#             user_id UUID NOT NULL,
#             route TEXT NOT NULL
#         );
#         """
#         logger.debug("Creating request_log table if not exists")
#         await self.connection_manager.execute_query(query)

#     async def _count_requests(
#         self,
#         user_id: UUID,
#         route: Optional[str],
#         since: datetime,
#     ) -> int:
#         """
#         Count how many requests a user (optionally for a specific route)
#         has made since the given datetime.
#         """
#         if route:
#             query = f"""
#             SELECT COUNT(*)::int
#             FROM {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
#             WHERE user_id = $1
#               AND route = $2
#               AND time >= $3
#             """
#             params = [user_id, route, since]
#             logger.debug(f"Counting requests for user={user_id}, route={route}")
#         else:
#             query = f"""
#             SELECT COUNT(*)::int
#             FROM {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
#             WHERE user_id = $1
#               AND time >= $2
#             """
#             params = [user_id, since]
#             logger.debug(f"Counting all requests for user={user_id}")

#         result = await self.connection_manager.fetchrow_query(query, params)
#         return result["count"] if result else 0

#     async def _count_monthly_requests(self, user_id: UUID) -> int:
#         """
#         Count the number of requests so far this month for a given user.
#         """
#         now = datetime.now(timezone.utc)
#         start_of_month = now.replace(
#             day=1, hour=0, minute=0, second=0, microsecond=0
#         )
#         return await self._count_requests(
#             user_id, route=None, since=start_of_month
#         )

#     def determine_effective_limits(
#         self, user: User, route: str
#     ) -> LimitSettings:
#         """
#         Determine the final effective limits for a user+route combination,
#         respecting:
#           1) Global defaults
#           2) Route-specific overrides
#           3) User-level overrides
#         """
#         # ------------------------
#         # 1) Start with global/base
#         # ------------------------
#         base_limits = self.config.limits

#         # We’ll make a copy so we don’t mutate self.config.limits directly
#         effective = LimitSettings(
#             global_per_min=base_limits.global_per_min,
#             route_per_min=base_limits.route_per_min,
#             monthly_limit=base_limits.monthly_limit,
#         )

#         # ------------------------
#         # 2) Route-level overrides
#         # ------------------------
#         route_config = self.config.route_limits.get(route)
#         if route_config:
#             if route_config.global_per_min is not None:
#                 effective.global_per_min = route_config.global_per_min
#             if route_config.route_per_min is not None:
#                 effective.route_per_min = route_config.route_per_min
#             if route_config.monthly_limit is not None:
#                 effective.monthly_limit = route_config.monthly_limit

#         # ------------------------
#         # 3) User-level overrides
#         # ------------------------
#         # The user object might have a dictionary of overrides
#         # which can include route_overrides, global_per_min, monthly_limit, etc.
#         user_overrides = user.limits_overrides or {}

#         # (a) "global" user overrides
#         if user_overrides.get("global_per_min") is not None:
#             effective.global_per_min = user_overrides["global_per_min"]
#         if user_overrides.get("monthly_limit") is not None:
#             effective.monthly_limit = user_overrides["monthly_limit"]

#         # (b) route-level user overrides
#         route_overrides = user_overrides.get("route_overrides", {})
#         specific_config = route_overrides.get(route, {})
#         if specific_config.get("global_per_min") is not None:
#             effective.global_per_min = specific_config["global_per_min"]
#         if specific_config.get("route_per_min") is not None:
#             effective.route_per_min = specific_config["route_per_min"]
#         if specific_config.get("monthly_limit") is not None:
#             effective.monthly_limit = specific_config["monthly_limit"]

#         return effective

#     async def check_limits(self, user: User, route: str):
#         """
#         Perform rate limit checks for a user on a specific route.

#         :param user: The fully-fetched User object with .limits_overrides, etc.
#         :param route: The route/path being accessed.
#         :raises ValueError: if any limit is exceeded.
#         """
#         user_id = user.id
#         now = datetime.now(timezone.utc)
#         one_min_ago = now - timedelta(minutes=1)

#         # 1) Compute the final (effective) limits for this user & route
#         limits = self.determine_effective_limits(user, route)

#         # 2) Check each of them in turn, if they exist
#         # ------------------------------------------------------------
#         # Global per-minute limit
#         # ------------------------------------------------------------
#         if limits.global_per_min is not None:
#             user_req_count = await self._count_requests(
#                 user_id, None, one_min_ago
#             )
#             if user_req_count > limits.global_per_min:
#                 logger.warning(
#                     f"Global per-minute limit exceeded for "
#                     f"user_id={user_id}, route={route}"
#                 )
#                 raise ValueError("Global per-minute rate limit exceeded")

#         # ------------------------------------------------------------
#         # Route-specific per-minute limit
#         # ------------------------------------------------------------
#         if limits.route_per_min is not None:
#             route_req_count = await self._count_requests(
#                 user_id, route, one_min_ago
#             )
#             if route_req_count > limits.route_per_min:
#                 logger.warning(
#                     f"Per-route per-minute limit exceeded for "
#                     f"user_id={user_id}, route={route}"
#                 )
#                 raise ValueError("Per-route per-minute rate limit exceeded")

#         # ------------------------------------------------------------
#         # Monthly limit
#         # ------------------------------------------------------------
#         if limits.monthly_limit is not None:
#             monthly_count = await self._count_monthly_requests(user_id)
#             if monthly_count > limits.monthly_limit:
#                 logger.warning(
#                     f"Monthly limit exceeded for user_id={user_id}, "
#                     f"route={route}"
#                 )
#                 raise ValueError("Monthly rate limit exceeded")

#     async def log_request(self, user_id: UUID, route: str):
#         """
#         Log a successful request to the request_log table.
#         """
#         query = f"""
#         INSERT INTO {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
#         (time, user_id, route)
#         VALUES (CURRENT_TIMESTAMP AT TIME ZONE 'UTC', $1, $2)
#         """
#         await self.connection_manager.execute_query(query, [user_id, route])
