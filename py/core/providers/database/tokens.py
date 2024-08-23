from datetime import datetime, timedelta
from typing import Optional

from .base import DatabaseMixin, QueryBuilder


class BlacklistedTokensMixin(DatabaseMixin):
    def create_table(self):
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
        self.execute_query(query)

    def blacklist_token(self, token: str, current_time: datetime = None):
        if current_time is None:
            current_time = datetime.utcnow()

        query, params = (
            QueryBuilder(self._get_table_name("blacklisted_tokens"))
            .insert({"token": token, "blacklisted_at": current_time})
            .build()
        )
        self.execute_query(query, params)

    def is_token_blacklisted(self, token: str) -> bool:
        query, params = (
            QueryBuilder(self._get_table_name("blacklisted_tokens"))
            .select(["1"])
            .where("token = :token", token=token)
            .limit(1)
            .build()
        )
        result = self.execute_query(query, params)
        return bool(result.fetchone())

    def clean_expired_blacklisted_tokens(
        self,
        max_age_hours: int = 7 * 24,
        current_time: Optional[datetime] = None,
    ):
        if current_time is None:
            current_time = datetime.utcnow()
        expiry_time = current_time - timedelta(hours=max_age_hours)

        query, params = (
            QueryBuilder(self._get_table_name("blacklisted_tokens"))
            .delete()
            .where("blacklisted_at < :expiry_time", expiry_time=expiry_time)
            .build()
        )
        self.execute_query(query, params)
