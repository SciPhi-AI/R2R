import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from core.base import Handler, R2RException

from .base import PostgresConnectionManager

logger = logging.getLogger()


class PostgresLimitsHandler(Handler):
    TABLE_NAME = "request_log"

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        route_limits: dict,
    ):
        super().__init__(project_name, connection_manager)
        self.route_limits = route_limits

    async def create_tables(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)} (
            time TIMESTAMPTZ NOT NULL,
            user_id UUID NOT NULL,
            route TEXT NOT NULL
        );
        """
        await self.connection_manager.execute_query(query)

    async def _count_requests(
        self, user_id: UUID, route: Optional[str], since: datetime
    ) -> int:
        if route:
            query = f"""
            SELECT COUNT(*)::int
            FROM {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
            WHERE user_id = $1
              AND route = $2
              AND time >= $3
            """
            params = [user_id, route, since]
        else:
            query = f"""
            SELECT COUNT(*)::int
            FROM {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
            WHERE user_id = $1
              AND time >= $2
            """
            params = [user_id, since]

        result = await self.connection_manager.fetchrow_query(query, params)
        return result["count"] if result else 0

    async def _count_monthly_requests(self, user_id: UUID) -> int:
        now = datetime.now(timezone.utc)
        start_of_month = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        return await self._count_requests(
            user_id, route=None, since=start_of_month
        )

    async def check_limits(self, user_id: UUID, route: str):
        limits = self.route_limits.get(
            route,
            {
                "global_per_min": 60,
                "route_per_min": 20,
                "monthly_limit": 10000,
            },
        )

        global_per_min = limits["global_per_min"]
        route_per_min = limits["route_per_min"]
        monthly_limit = limits["monthly_limit"]

        now = datetime.now(timezone.utc)
        one_min_ago = now - timedelta(minutes=1)

        # Global per-minute check
        user_req_count = await self._count_requests(user_id, None, one_min_ago)
        print('min req count = ', user_req_count)
        if user_req_count >= global_per_min:
            raise ValueError("Global per-minute rate limit exceeded")

        # Per-route per-minute check
        route_req_count = await self._count_requests(user_id, route, one_min_ago)
        if route_req_count >= route_per_min:
            raise ValueError("Per-route per-minute rate limit exceeded")

        # Monthly limit check
        monthly_count = await self._count_monthly_requests(user_id)
        print('monthly_count = ', monthly_count)

        if monthly_count >= monthly_limit:
            raise ValueError("Monthly rate limit exceeded")

    async def log_request(self, user_id: UUID, route: str):
        query = f"""
        INSERT INTO {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)} (time, user_id, route)
        VALUES (CURRENT_TIMESTAMP AT TIME ZONE 'UTC', $1, $2)
        """
        await self.connection_manager.execute_query(query, [user_id, route])



# import logging
# from datetime import datetime, timedelta
# from typing import Optional
# from uuid import UUID

# from core.base import Handler, R2RException

# from .base import PostgresConnectionManager

# logger = logging.getLogger()


# class PostgresLimitsHandler(Handler):
#     TABLE_NAME = "request_log"

#     def __init__(
#         self,
#         project_name: str,
#         connection_manager: PostgresConnectionManager,
#         route_limits: dict,
#     ):
#         super().__init__(project_name, connection_manager)
#         self.route_limits = route_limits

#     async def create_tables(self):
#         """
#         Create the request_log table if it doesn't exist.
#         """
#         query = f"""
#         CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)} (
#             time TIMESTAMPTZ NOT NULL,
#             user_id UUID NOT NULL,
#             route TEXT NOT NULL
#         );
#         """
#         await self.connection_manager.execute_query(query)

#     async def _count_requests(
#         self, user_id: UUID, route: Optional[str], since: datetime
#     ) -> int:
#         if route:
#             query = f"""
#             SELECT COUNT(*)::int
#             FROM {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
#             WHERE user_id = $1
#               AND route = $2
#               AND time >= $3
#             """
#             params = [user_id, route, since]
#         else:
#             query = f"""
#             SELECT COUNT(*)::int
#             FROM {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
#             WHERE user_id = $1
#               AND time >= $2
#             """
#             params = [user_id, since]

#         result = await self.connection_manager.fetchrow_query(query, params)
#         return result["count"] if result else 0

#     async def _count_monthly_requests(self, user_id: UUID) -> int:
#         now = datetime.utcnow()
#         start_of_month = now.replace(
#             day=1, hour=0, minute=0, second=0, microsecond=0
#         )
#         return await self._count_requests(
#             user_id, route=None, since=start_of_month
#         )

#     async def check_limits(self, user_id: UUID, route: str):
#         """
#         Check if the user can proceed with the request, using route-specific limits.
#         Raises ValueError if the user exceeded any limit.
#         """
#         limits = self.route_limits.get(
#             route,
#             {
#                 "global_per_min": 60,  # default global per min
#                 "route_per_min": 20,  # default route per min
#                 "monthly_limit": 10000,  # default monthly limit
#             },
#         )

#         global_per_min = limits["global_per_min"]
#         route_per_min = limits["route_per_min"]
#         monthly_limit = limits["monthly_limit"]

#         now = datetime.utcnow()
#         one_min_ago = now - timedelta(minutes=1)

#         # Global per-minute check
#         user_req_count = await self._count_requests(user_id, None, one_min_ago)
#         print('min req count = ', user_req_count)
#         if user_req_count >= global_per_min:
#             raise ValueError("Global per-minute rate limit exceeded")

#         # Per-route per-minute check
#         route_req_count = await self._count_requests(
#             user_id, route, one_min_ago
#         )
#         if route_req_count >= route_per_min:
#             raise ValueError("Per-route per-minute rate limit exceeded")

#         # Monthly limit check
#         monthly_count = await self._count_monthly_requests(user_id)
#         print('monthly_count = ', monthly_count)

#         if monthly_count >= monthly_limit:
#             raise ValueError("Monthly rate limit exceeded")

#     async def log_request(self, user_id: UUID, route: str):
#         query = f"""
#         INSERT INTO {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)} (time, user_id, route)
#         VALUES (NOW(), $1, $2)
#         """
#         await self.connection_manager.execute_query(query, [user_id, route])
