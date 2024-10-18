import logging
from typing import Optional

import asyncpg

from core.base import CryptoProvider, DatabaseConfig
from core.providers.database.base import DatabaseMixin
from core.providers.database.collection import CollectionMixin
from core.providers.database.document import DocumentMixin
from core.providers.database.tokens import BlacklistedTokensMixin
from core.providers.database.user import UserMixin
from core.providers.database.vector import VectorDBMixin
from shared.abstractions.vector import VectorQuantizationType

logger = logging.getLogger()


class PostgresHandle(
    DocumentMixin,
    CollectionMixin,
    BlacklistedTokensMixin,
    UserMixin,
    VectorDBMixin,
):
    def __init__(
        self,
        config: DatabaseConfig,
        connection_string: str,
        crypto_provider: CryptoProvider,
        project_name: str,
        dimension: int,
        quantization_type: Optional[VectorQuantizationType] = None,
    ):
        super().__init__(config)
        self.config = config
        self.connection_string = connection_string
        self.crypto_provider = crypto_provider
        self.project_name = project_name
        self.dimension = dimension
        self.quantization_type = quantization_type
        self.pool = None

    def _get_table_name(self, base_name: str) -> str:
        return f"{self.project_name}.{base_name}"

    async def initialize(self, pool: asyncpg.pool.Pool):
        logger.info("Initializing `PostgresHandle` with connection pool.")

        self.pool = pool

        async with self.pool.get_connection() as conn:
            await conn.execute(f'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

            # Call create_table for each mixin
            for base_class in self.__class__.__bases__:
                if issubclass(base_class, DatabaseMixin):
                    await base_class.create_table(self)

        await self.initialize_vector_db()

        logger.info("Successfully initialized `PostgresHandle`")

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def execute_query(self, query, params=None, isolation_level=None):
        async with self.pool.acquire() as conn:
            if isolation_level:
                async with conn.transaction(isolation=isolation_level):
                    if params:
                        return await conn.execute(query, *params)
                    else:
                        return await conn.execute(query)
            else:
                if params:
                    return await conn.execute(query, *params)
                else:
                    return await conn.execute(query)

    async def execute_many(self, query, params=None, batch_size=1000):
        async with self.pool.get_connection() as conn:
            async with conn.transaction():
                if params:
                    for i in range(0, len(params), batch_size):
                        param_batch = params[i : i + batch_size]
                        await conn.executemany(query, param_batch)
                else:
                    await conn.executemany(query)

    async def fetch_query(self, query, params=None):
        async with self.pool.get_connection() as conn:
            async with conn.transaction():
                return (
                    await conn.fetch(query, *params)
                    if params
                    else await conn.fetch(query)
                )

    async def fetchrow_query(self, query, params=None):
        async with self.pool.get_connection() as conn:
            async with conn.transaction():
                if params:
                    return await conn.fetchrow(query, *params)
                else:
                    return await conn.fetchrow(query)
