from datetime import datetime, timedelta
from typing import Optional

from .base import DatabaseMixin


class BlacklistedTokensMixin(DatabaseMixin):
    async def create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('blacklisted_tokens')} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            token TEXT NOT NULL,
            blacklisted_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_blacklisted_tokens_{self.collection_name}_token
        ON {self._get_table_name('blacklisted_tokens')} (token);
        CREATE INDEX IF NOT EXISTS idx_blacklisted_tokens_{self.collection_name}_blacklisted_at
        ON {self._get_table_name('blacklisted_tokens')} (blacklisted_at);
        """
        await self.execute_query(query)

    async def blacklist_token(self, token: str, current_time: datetime = None):
        if current_time is None:
            current_time = datetime.utcnow()

        query = f"""
        INSERT INTO {self._get_table_name("blacklisted_tokens")} (token, blacklisted_at)
        VALUES ($1, $2)
        """
        await self.execute_query(query, [token, current_time])

    async def is_token_blacklisted(self, token: str) -> bool:
        query = f"""
        SELECT 1 FROM {self._get_table_name("blacklisted_tokens")}
        WHERE token = $1
        LIMIT 1
        """
        result = await self.fetchrow_query(query, [token])
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
        DELETE FROM {self._get_table_name("blacklisted_tokens")}
        WHERE blacklisted_at < $1
        """
        await self.execute_query(query, [expiry_time])
