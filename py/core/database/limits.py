import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from core.base import Handler

from ..base.providers.database import DatabaseConfig, LimitSettings
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
            logger.debug(f"Counting requests for route {route}")
        else:
            query = f"""
            SELECT COUNT(*)::int
            FROM {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)}
            WHERE user_id = $1
              AND time >= $2
            """
            params = [user_id, since]
            logger.debug("Counting all requests")

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

    def _determine_limits_for(
        self, user_id: UUID, route: str
    ) -> LimitSettings:
        # Start with base limits
        limits = self.config.limits

        # Route-specific limits - directly override if present
        if route_limits := self.config.route_limits.get(route):
            # Only override non-None values from route_limits
            if route_limits.global_per_min is not None:
                limits.global_per_min = route_limits.global_per_min
            if route_limits.route_per_min is not None:
                limits.route_per_min = route_limits.route_per_min
            if route_limits.monthly_limit is not None:
                limits.monthly_limit = route_limits.monthly_limit

        # User-specific limits - directly override if present
        if user_limits := self.config.user_limits.get(user_id):
            # Only override non-None values from user_limits
            if user_limits.global_per_min is not None:
                limits.global_per_min = user_limits.global_per_min
            if user_limits.route_per_min is not None:
                limits.route_per_min = user_limits.route_per_min
            if user_limits.monthly_limit is not None:
                limits.monthly_limit = user_limits.monthly_limit

        return limits

    async def check_limits(self, user_id: UUID, route: str):
        # Determine final applicable limits
        if limits := self._determine_limits_for(user_id, route):
            limits = self.config.default_limits

        global_per_min = limits.global_per_min
        route_per_min = limits.route_per_min
        monthly_limit = limits.monthly_limit

        now = datetime.now(timezone.utc)
        one_min_ago = now - timedelta(minutes=1)

        # Global per-minute check
        if global_per_min is not None:
            user_req_count = await self._count_requests(
                user_id, None, one_min_ago
            )
            if user_req_count > global_per_min:
                logger.warning(
                    f"Global per-minute limit exceeded for user_id={user_id}, route={route}"
                )
                raise ValueError("Global per-minute rate limit exceeded")

        # Per-route per-minute check
        if route_per_min is not None:
            route_req_count = await self._count_requests(
                user_id, route, one_min_ago
            )
            if route_req_count > route_per_min:
                logger.warning(
                    f"Per-route per-minute limit exceeded for user_id={user_id}, route={route}"
                )
                raise ValueError("Per-route per-minute rate limit exceeded")

        # Monthly limit check
        if monthly_limit is not None:
            monthly_count = await self._count_monthly_requests(user_id)
            if monthly_count > monthly_limit:
                logger.warning(
                    f"Monthly limit exceeded for user_id={user_id}, route={route}"
                )
                raise ValueError("Monthly rate limit exceeded")

    async def log_request(self, user_id: UUID, route: str):
        query = f"""
        INSERT INTO {self._get_table_name(PostgresLimitsHandler.TABLE_NAME)} (time, user_id, route)
        VALUES (CURRENT_TIMESTAMP AT TIME ZONE 'UTC', $1, $2)
        """
        await self.connection_manager.execute_query(query, [user_id, route])
