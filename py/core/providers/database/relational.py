import logging

import asyncpg

from core.providers.database.base import DatabaseMixin
from core.providers.database.document import DocumentMixin
from core.providers.database.group import GroupMixin
from core.providers.database.tokens import BlacklistedTokensMixin
from core.providers.database.user import UserMixin

logger = logging.getLogger(__name__)


class PostgresRelationalDBProvider(
    GroupMixin,
    UserMixin,
    BlacklistedTokensMixin,
    DocumentMixin,
):
    def __init__(
        self, config, connection_string, crypto_provider, collection_name
    ):
        self.config = config
        self.connection_string = connection_string
        self.crypto_provider = crypto_provider
        self.collection_name = collection_name
        super().__init__()

    async def initialize(self):
        try:
            self.conn = await asyncpg.connect(self.connection_string)
            logger.info("Successfully connected to relational database.")
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to relational database."
            ) from e

        await self._initialize_relational_db()

    def _get_table_name(self, base_name: str) -> str:
        return f"{base_name}_{self.collection_name}"

    async def execute_query(self, query, params=None):
        if params:
            return await self.conn.execute(query, *params)
        else:
            return await self.conn.execute(query)

    async def _initialize_relational_db(self):
        await self.conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

        # Call create_table for each mixin
        for base_class in self.__class__.__bases__:
            if issubclass(base_class, DatabaseMixin):
                await base_class.create_table(self)
