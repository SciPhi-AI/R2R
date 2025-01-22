from datetime import datetime, timedelta
from typing import Optional

from core.base import Handler

from .base import PostgresConnectionManager


class PostgresTokensHandler(Handler):
    TABLE_NAME = "blacklisted_tokens"

    def __init__(
        self, project_name: str, connection_manager: PostgresConnectionManager
    ):
        super().__init__(project_name, connection_manager)

    async def create_tables(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresTokensHandler.TABLE_NAME)} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            token TEXT NOT NULL,
            blacklisted_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_{self.project_name}_{PostgresTokensHandler.TABLE_NAME}_token
        ON {self._get_table_name(PostgresTokensHandler.TABLE_NAME)} (token);
        CREATE INDEX IF NOT EXISTS idx_{self.project_name}_{PostgresTokensHandler.TABLE_NAME}_blacklisted_at
        ON {self._get_table_name(PostgresTokensHandler.TABLE_NAME)} (blacklisted_at);
        """
        await self.connection_manager.execute_query(query)

    async def blacklist_token(
        self, token: str, current_time: Optional[datetime] = None
    ):
        if current_time is None:
            current_time = datetime.utcnow()

        query = f"""
        INSERT INTO {self._get_table_name(PostgresTokensHandler.TABLE_NAME)} (token, blacklisted_at)
        VALUES ($1, $2)
        """
        await self.connection_manager.execute_query(
            query, [token, current_time]
        )

    async def is_token_blacklisted(self, token: str) -> bool:
        query = f"""
        SELECT 1 FROM {self._get_table_name(PostgresTokensHandler.TABLE_NAME)}
        WHERE token = $1
        LIMIT 1
        """
        result = await self.connection_manager.fetchrow_query(query, [token])
        return bool(result)

    async def clean_expired_blacklisted_tokens(
        self,
        max_age_hours: int = 7 * 24,
        current_time: Optional[datetime] = None,
    ):
        if current_time is None:
            current_time = datetime.utcnow()
        expiry_time = current_time - timedelta(hours=max_age_hours)

        query = f"""
        DELETE FROM {self._get_table_name(PostgresTokensHandler.TABLE_NAME)}
        WHERE blacklisted_at < $1
        """
        await self.connection_manager.execute_query(query, [expiry_time])
