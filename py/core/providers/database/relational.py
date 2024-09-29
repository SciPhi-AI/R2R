import logging
from contextlib import asynccontextmanager

import asyncpg

from core.base import RelationalDBProvider
from core.providers.database.base import DatabaseMixin
from core.providers.database.collection import CollectionMixin
from core.providers.database.document import DocumentMixin
from core.providers.database.tokens import BlacklistedTokensMixin
from core.providers.database.user import UserMixin

logger = logging.getLogger(__name__)


class PostgresRelationalDBProvider(
    RelationalDBProvider,
    DocumentMixin,
    CollectionMixin,
    BlacklistedTokensMixin,
    UserMixin,
):
    def __init__(
        self,
        config,
        connection_string,
        crypto_provider,
        project_name,
        postgres_configuration_settings,
    ):
        super().__init__(config)
        self.config = config
        self.connection_string = connection_string
        self.crypto_provider = crypto_provider
        self.project_name = project_name
        self.pool = None
        self.postgres_configuration_settings = postgres_configuration_settings

    async def initialize(self):
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                max_size=self.postgres_configuration_settings.max_connections,
            )
            logger.info(
                "Successfully connected to Postgres database and created connection pool."
            )
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to relational database."
            ) from e

        await self._initialize_relational_db()

    def _get_table_name(self, base_name: str) -> str:
        return f"{self.project_name}.{base_name}"

    @asynccontextmanager
    async def get_connection(self):
        async with self.pool.acquire() as conn:
            yield conn

    async def execute_query(self, query, params=None):
        async with self.get_connection() as conn:
            async with conn.transaction():
                if params:
                    return await conn.execute(query, *params)
                else:
                    return await conn.execute(query)

    async def execute_many(self, query, params=None, batch_size=1000):
        async with self.get_connection() as conn:
            async with conn.transaction():
                if params:
                    for i in range(0, len(params), batch_size):
                        param_batch = params[i : i + batch_size]
                        await conn.executemany(query, param_batch)
                else:
                    await conn.executemany(query)

    async def fetch_query(self, query, params=None):
        async with self.get_connection() as conn:
            async with conn.transaction():
                return (
                    await conn.fetch(query, *params)
                    if params
                    else await conn.fetch(query)
                )

    async def fetchrow_query(self, query, params=None):
        async with self.get_connection() as conn:
            async with conn.transaction():
                if params:
                    return await conn.fetchrow(query, *params)
                else:
                    return await conn.fetchrow(query)

    # async def copy_records_to_table(self, table_name, records):
    #     async with self.get_connection() as conn:
    #         async with conn.transaction():
    #             await conn.copy_records_to_table(table_name, records)

    async def _initialize_relational_db(self):
        async with self.get_connection() as conn:
            await conn.execute(f'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

            # Call create_table for each mixin
            for base_class in self.__class__.__bases__:
                if issubclass(base_class, DatabaseMixin):
                    await base_class.create_table(self)

    async def close(self):
        if self.pool:
            await self.pool.close()
