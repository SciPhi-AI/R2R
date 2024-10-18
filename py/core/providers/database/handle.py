from typing import Optional

from core.base import CryptoProvider, DatabaseConfig
from core.providers.database.base import (
    DatabaseMixin,
    SemaphoreConnectionPool,
    logger,
)
from core.providers.database.collection import CollectionMixin
from core.providers.database.document import DocumentMixin
from core.providers.database.tokens import BlacklistedTokensMixin
from core.providers.database.user import UserMixin
from core.providers.database.vector import VectorDBMixin
from shared.abstractions.vector import VectorQuantizationType


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
        pool_size: int = 10,
        max_retries: int = 3,
        retry_delay: int = 1,
    ):
        self.config = config
        self.connection_string = connection_string
        self.crypto_provider = crypto_provider
        self.project_name = project_name
        self.dimension = dimension
        self.quantization_type = quantization_type
        self.pool_size = pool_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.pool: Optional[SemaphoreConnectionPool] = None

    def _get_table_name(self, base_name: str) -> str:
        return f"{self.project_name}.{base_name}"

    async def initialize(self, pool: SemaphoreConnectionPool):
        logger.info("Initializing `PostgresDBHandle`.")
        self.pool = pool

        async with self.pool.get_connection() as conn:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;")

            # Create schema if it doesn't exist
            await conn.execute(
                f'CREATE SCHEMA IF NOT EXISTS "{self.project_name}";'
            )

            # Call create_table for each mixin
            for base_class in self.__class__.__bases__:
                if issubclass(base_class, DatabaseMixin):
                    await base_class.create_table(self)

        logger.info("Successfully initialized `PostgresDBHandle`")

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def execute_query(self, query, params=None, isolation_level=None):
        async with self.pool.get_connection() as conn:
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

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
