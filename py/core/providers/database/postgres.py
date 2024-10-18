# TODO: Clean this up and make it more congruent across the vector database and the relational database.
import logging
import os
import warnings
from typing import Any, Optional

from core.base import (
    CryptoProvider,
    DatabaseConfig,
    DatabaseProvider,
    PostgresConfigurationSettings,
    VectorQuantizationType,
)

from .base import SemaphoreConnectionPool,     DatabaseMixin



from core.providers.database.collection import CollectionMixin
from core.providers.database.document import DocumentMixin
from core.providers.database.tokens import BlacklistedTokensMixin
from core.providers.database.user import UserMixin
from core.providers.database.vector import VectorDBMixin
from shared.abstractions.vector import VectorQuantizationType


logger = logging.getLogger()

def get_env_var(new_var, old_var, config_value):
    value = config_value or os.getenv(new_var) or os.getenv(old_var)
    if os.getenv(old_var) and not os.getenv(new_var):
        warnings.warn(
            f"{old_var} is deprecated and support for it will be removed in release 3.5.0. Use {new_var} instead."
        )
    return value


class PostgresDBProvider(
    DatabaseProvider,
    DocumentMixin,
    CollectionMixin,
    BlacklistedTokensMixin,
    UserMixin,
    VectorDBMixin,

    ):
    user: str
    password: str
    host: str
    port: int
    db_name: str
    project_name: str
    connection_string: str
    dimension: int
    conn: Optional[Any]
    crypto_provider: CryptoProvider
    postgres_configuration_settings: PostgresConfigurationSettings
    default_collection_name: str
    default_collection_description: str

    def __init__(
        self,
        config: DatabaseConfig,
        dimension: int,
        crypto_provider: CryptoProvider,
        quantization_type: Optional[
            VectorQuantizationType
        ] = VectorQuantizationType.FP32,
        *args,
        **kwargs,
    ):
        super().__init__(config)

        env_vars = [
            ("user", "R2R_POSTGRES_USER", "POSTGRES_USER"),
            ("password", "R2R_POSTGRES_PASSWORD", "POSTGRES_PASSWORD"),
            ("host", "R2R_POSTGRES_HOST", "POSTGRES_HOST"),
            ("port", "R2R_POSTGRES_PORT", "POSTGRES_PORT"),
            ("db_name", "R2R_POSTGRES_DBNAME", "POSTGRES_DBNAME"),
        ]

        for attr, new_var, old_var in env_vars:
            if value := get_env_var(new_var, old_var, getattr(config, attr)):
                setattr(self, attr, value)
            else:
                raise ValueError(
                    f"Error, please set a valid {new_var} environment variable or set a '{attr}' in the 'database' settings of your `r2r.toml`."
                )

        self.port = int(self.port)

        self.project_name = (
            get_env_var(
                "R2R_PROJECT_NAME",
                "R2R_POSTGRES_PROJECT_NAME",  # Remove this after deprecation
                config.app.project_name,
            )
            or "r2r_default"
        )

        if not self.project_name:
            raise ValueError(
                "Error, please set a valid R2R_PROJECT_NAME environment variable or set a 'project_name' in the 'database' settings of your `r2r.toml`."
            )

        # Check if it's a Unix socket connection
        if self.host.startswith("/") and not self.port:
            self.connection_string = f"postgresql://{self.user}:{self.password}@/{self.db_name}?host={self.host}"
            logger.info("Connecting to Postgres via Unix socket")
        else:
            self.connection_string = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"
            logger.info("Connecting to Postgres via TCP/IP")

        self.dimension = dimension
        self.vector_db_quantization_type = quantization_type
        self.conn = None
        self.config: DatabaseConfig = config
        self.crypto_provider = crypto_provider
        self.postgres_configuration_settings: PostgresConfigurationSettings = (
            self._get_postgres_configuration_settings(config)
        )
        self.default_collection_name = config.default_collection_name
        self.default_collection_description = (
            config.default_collection_description
        )

        self.pool: Optional[SemaphoreConnectionPool] = None

    def _get_table_name(self, base_name: str) -> str:
        return f"{self.project_name}.{base_name}"

    async def initialize(self):
        logger.info("Initializing `PostgresDBProvider`.")
        self.pool = SemaphoreConnectionPool(
            self.connection_string, self.postgres_configuration_settings
        )
        await self.pool.initialize()

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
        logger.info("Successfully initialized `PostgresDBProvider`")

    def _get_postgres_configuration_settings(
        self, config: DatabaseConfig
    ) -> PostgresConfigurationSettings:
        settings = PostgresConfigurationSettings()

        env_mapping = {
            "max_connections": "R2R_POSTGRES_MAX_CONNECTIONS",
            "shared_buffers": "R2R_POSTGRES_SHARED_BUFFERS",
            "effective_cache_size": "R2R_POSTGRES_EFFECTIVE_CACHE_SIZE",
            "maintenance_work_mem": "R2R_POSTGRES_MAINTENANCE_WORK_MEM",
            "checkpoint_completion_target": "R2R_POSTGRES_CHECKPOINT_COMPLETION_TARGET",
            "wal_buffers": "R2R_POSTGRES_WAL_BUFFERS",
            "default_statistics_target": "R2R_POSTGRES_DEFAULT_STATISTICS_TARGET",
            "random_page_cost": "R2R_POSTGRES_RANDOM_PAGE_COST",
            "effective_io_concurrency": "R2R_POSTGRES_EFFECTIVE_IO_CONCURRENCY",
            "work_mem": "R2R_POSTGRES_WORK_MEM",
            "huge_pages": "R2R_POSTGRES_HUGE_PAGES",
            "min_wal_size": "R2R_POSTGRES_MIN_WAL_SIZE",
            "max_wal_size": "R2R_POSTGRES_MAX_WAL_SIZE",
            "max_worker_processes": "R2R_POSTGRES_MAX_WORKER_PROCESSES",
            "max_parallel_workers_per_gather": "R2R_POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER",
            "max_parallel_workers": "R2R_POSTGRES_MAX_PARALLEL_WORKERS",
            "max_parallel_maintenance_workers": "R2R_POSTGRES_MAX_PARALLEL_MAINTENANCE_WORKERS",
        }

        for setting, env_var in env_mapping.items():
            value = getattr(
                config.postgres_configuration_settings, setting, None
            ) or os.getenv(env_var)

            if value is not None and value != "":
                field_type = settings.__annotations__[setting]
                if field_type == Optional[int]:
                    value = int(value)
                elif field_type == Optional[float]:
                    value = float(value)

                setattr(settings, setting, value)

        return settings

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
            print('query', query)
            print('params', params)
            
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
