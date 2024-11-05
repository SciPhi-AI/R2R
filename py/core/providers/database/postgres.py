# TODO: Clean this up and make it more congruent across the vector database and the relational database.
import logging
import os
import warnings
from typing import Any, Optional

from core.base import (
    DatabaseConfig,
    DatabaseConnectionManager,
    DatabaseProvider,
    PostgresConfigurationSettings,
    VectorQuantizationType,
    UserConfig,
)
from core.providers import BCryptProvider
from core.providers.database.base import PostgresConnectionManager
from core.providers.database.collection import PostgresCollectionHandler
from core.providers.database.document import PostgresDocumentHandler
from core.providers.database.file import PostgresFileHandler
from core.providers.database.kg import PostgresKGHandler
from core.providers.database.logging import PostgresLoggingHandler
from core.providers.database.prompt import PostgresPromptHandler
from core.providers.database.tokens import PostgresTokenHandler
from core.providers.database.user import PostgresUserHandler
from core.providers.database.vector import PostgresVectorHandler

from .base import SemaphoreConnectionPool

logger = logging.getLogger()


def get_env_var(new_var, old_var, config_value):
    value = config_value or os.getenv(new_var) or os.getenv(old_var)
    if os.getenv(old_var) and not os.getenv(new_var):
        warnings.warn(
            f"{old_var} is deprecated and support for it will be removed in release 3.5.0. Use {new_var} instead."
        )
    return value


class PostgresDBProvider(DatabaseProvider):
    # R2R configuration settings
    config: DatabaseConfig
    project_name: str

    # Postgres connection settings
    user: str
    password: str
    host: str
    port: int
    db_name: str
    connection_string: str
    dimension: int
    conn: Optional[Any]

    crypto_provider: BCryptProvider
    user_config: UserConfig
    postgres_configuration_settings: PostgresConfigurationSettings
    default_collection_name: str
    default_collection_description: str

    connection_manager: PostgresConnectionManager
    document_handler: PostgresDocumentHandler
    collection_handler: PostgresCollectionHandler
    token_handler: PostgresTokenHandler
    user_handler: PostgresUserHandler
    vector_handler: PostgresVectorHandler
    kg_handler: PostgresKGHandler
    prompt_handler: PostgresPromptHandler
    file_handler: PostgresFileHandler
    logging_handler: PostgresLoggingHandler

    def __init__(
        self,
        config: DatabaseConfig,
        dimension: int,
        crypto_provider: BCryptProvider,
        quantization_type: VectorQuantizationType = VectorQuantizationType.FP32,
        *args,
        **kwargs,
    ):
        super().__init__(config)

        # Get user config from app config
        self.user_config = getattr(config.app, "user", UserConfig())
        logger.info(
            f"Initialized database with user roles: {list(self.user_config.roles.keys())}"
        )

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
        self.quantization_type = quantization_type
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
        self.enable_fts = config.enable_fts

        self.connection_manager: PostgresConnectionManager = (
            PostgresConnectionManager()
        )
        self.document_handler = PostgresDocumentHandler(
            self.project_name, self.connection_manager
        )
        self.token_handler = PostgresTokenHandler(
            self.project_name, self.connection_manager
        )
        self.collection_handler = PostgresCollectionHandler(
            self.project_name, self.connection_manager, self.config
        )
        self.user_handler = PostgresUserHandler(
            self.project_name,
            self.connection_manager,
            self.crypto_provider,
            self.user_config,
        )
        self.vector_handler = PostgresVectorHandler(
            self.project_name,
            self.connection_manager,
            self.dimension,
            self.quantization_type,
            self.enable_fts,
        )
        self.kg_handler = PostgresKGHandler(
            self.project_name,
            self.connection_manager,
            self.collection_handler,
            self.dimension,
            self.quantization_type,
        )
        self.prompt_handler = PostgresPromptHandler(
            self.project_name, self.connection_manager
        )
        self.file_handler = PostgresFileHandler(
            self.project_name, self.connection_manager
        )
        self.logging_handler = PostgresLoggingHandler(
            self.project_name, self.connection_manager
        )

        # Extract UserConfig from the main config
        self.user_config = getattr(config.app, "user", UserConfig())
        logger.info(
            f"Initialized database with user roles: {list(self.user_config.roles.keys())}"
        )
        logger.info(f"Default role: {self.user_config.default_role}")

    async def initialize(self):
        logger.info("Initializing `PostgresDBProvider`.")
        self.pool = SemaphoreConnectionPool(
            self.connection_string, self.postgres_configuration_settings
        )
        await self.pool.initialize()
        await self.connection_manager.initialize(self.pool)

        async with self.pool.get_connection() as conn:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;")

            # Create schema if it doesn't exist
            await conn.execute(
                f'CREATE SCHEMA IF NOT EXISTS "{self.project_name}";'
            )

        await self.document_handler.create_tables()
        await self.collection_handler.create_tables()
        await self.token_handler.create_tables()
        await self.user_handler.create_tables()
        await self.vector_handler.create_tables()
        await self.prompt_handler.create_tables()
        await self.file_handler.create_tables()
        await self.kg_handler.create_tables()
        await self.logging_handler.create_tables()

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

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
