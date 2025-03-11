# TODO: Clean this up and make it more congruent across the vector database and the relational database.
import logging
import os
from typing import TYPE_CHECKING, Any, Optional

from ...base.abstractions import VectorQuantizationType
from ...base.providers import (
    DatabaseConfig,
    DatabaseProvider,
    PostgresConfigurationSettings,
)
from .base import PostgresConnectionManager, SemaphoreConnectionPool
from .chunks import PostgresChunksHandler
from .collections import PostgresCollectionsHandler
from .conversations import PostgresConversationsHandler
from .documents import PostgresDocumentsHandler
from .files import PostgresFilesHandler
from .graphs import (
    PostgresCommunitiesHandler,
    PostgresEntitiesHandler,
    PostgresGraphsHandler,
    PostgresRelationshipsHandler,
)
from .limits import PostgresLimitsHandler
from .prompts_handler import PostgresPromptsHandler
from .tokens import PostgresTokensHandler
from .users import PostgresUserHandler

if TYPE_CHECKING:
    from ..crypto import BCryptCryptoProvider, NaClCryptoProvider

    CryptoProviderType = BCryptCryptoProvider | NaClCryptoProvider

logger = logging.getLogger()


class PostgresDatabaseProvider(DatabaseProvider):
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
    dimension: int | float
    conn: Optional[Any]

    crypto_provider: "CryptoProviderType"
    postgres_configuration_settings: PostgresConfigurationSettings
    default_collection_name: str
    default_collection_description: str

    connection_manager: PostgresConnectionManager
    documents_handler: PostgresDocumentsHandler
    collections_handler: PostgresCollectionsHandler
    token_handler: PostgresTokensHandler
    users_handler: PostgresUserHandler
    chunks_handler: PostgresChunksHandler
    entities_handler: PostgresEntitiesHandler
    communities_handler: PostgresCommunitiesHandler
    relationships_handler: PostgresRelationshipsHandler
    graphs_handler: PostgresGraphsHandler
    prompts_handler: PostgresPromptsHandler
    files_handler: PostgresFilesHandler
    conversations_handler: PostgresConversationsHandler
    limits_handler: PostgresLimitsHandler

    def __init__(
        self,
        config: DatabaseConfig,
        dimension: int | float,
        crypto_provider: "BCryptCryptoProvider | NaClCryptoProvider",
        quantization_type: VectorQuantizationType = VectorQuantizationType.FP32,
        *args,
        **kwargs,
    ):
        super().__init__(config)

        env_vars = [
            ("user", "R2R_POSTGRES_USER"),
            ("password", "R2R_POSTGRES_PASSWORD"),
            ("host", "R2R_POSTGRES_HOST"),
            ("port", "R2R_POSTGRES_PORT"),
            ("db_name", "R2R_POSTGRES_DBNAME"),
        ]

        for attr, env_var in env_vars:
            if value := (getattr(config, attr) or os.getenv(env_var)):
                setattr(self, attr, value)
            else:
                raise ValueError(
                    f"Error, please set a valid {env_var} environment variable or set a '{attr}' in the 'database' settings of your `r2r.toml`."
                )

        self.port = int(self.port)

        self.project_name = (
            config.app.project_name
            or os.getenv("R2R_PROJECT_NAME")
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

        self.connection_manager: PostgresConnectionManager = (
            PostgresConnectionManager()
        )
        self.documents_handler = PostgresDocumentsHandler(
            project_name=self.project_name,
            connection_manager=self.connection_manager,
            dimension=self.dimension,
        )
        self.token_handler = PostgresTokensHandler(
            self.project_name, self.connection_manager
        )
        self.collections_handler = PostgresCollectionsHandler(
            self.project_name, self.connection_manager, self.config
        )
        self.users_handler = PostgresUserHandler(
            self.project_name, self.connection_manager, self.crypto_provider
        )
        self.chunks_handler = PostgresChunksHandler(
            project_name=self.project_name,
            connection_manager=self.connection_manager,
            dimension=self.dimension,
            quantization_type=(self.quantization_type),
        )
        self.conversations_handler = PostgresConversationsHandler(
            self.project_name, self.connection_manager
        )
        self.entities_handler = PostgresEntitiesHandler(
            project_name=self.project_name,
            connection_manager=self.connection_manager,
            collections_handler=self.collections_handler,
            dimension=self.dimension,
            quantization_type=self.quantization_type,
        )
        self.relationships_handler = PostgresRelationshipsHandler(
            project_name=self.project_name,
            connection_manager=self.connection_manager,
            collections_handler=self.collections_handler,
            dimension=self.dimension,
            quantization_type=self.quantization_type,
        )
        self.communities_handler = PostgresCommunitiesHandler(
            project_name=self.project_name,
            connection_manager=self.connection_manager,
            collections_handler=self.collections_handler,
            dimension=self.dimension,
            quantization_type=self.quantization_type,
        )
        self.graphs_handler = PostgresGraphsHandler(
            project_name=self.project_name,
            connection_manager=self.connection_manager,
            collections_handler=self.collections_handler,
            dimension=self.dimension,
            quantization_type=self.quantization_type,
        )
        self.prompts_handler = PostgresPromptsHandler(
            self.project_name, self.connection_manager
        )
        self.files_handler = PostgresFilesHandler(
            self.project_name, self.connection_manager
        )

        self.limits_handler = PostgresLimitsHandler(
            project_name=self.project_name,
            connection_manager=self.connection_manager,
            config=self.config,
        )

    async def initialize(self):
        logger.info("Initializing `PostgresDatabaseProvider`.")
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

        await self.documents_handler.create_tables()
        await self.collections_handler.create_tables()
        await self.token_handler.create_tables()
        await self.users_handler.create_tables()
        await self.chunks_handler.create_tables()
        await self.prompts_handler.create_tables()
        await self.files_handler.create_tables()
        await self.graphs_handler.create_tables()
        await self.communities_handler.create_tables()
        await self.entities_handler.create_tables()
        await self.relationships_handler.create_tables()
        await self.conversations_handler.create_tables()
        await self.limits_handler.create_tables()

    def _get_postgres_configuration_settings(
        self, config: DatabaseConfig
    ) -> PostgresConfigurationSettings:
        settings = PostgresConfigurationSettings()

        env_mapping = {
            "checkpoint_completion_target": "R2R_POSTGRES_CHECKPOINT_COMPLETION_TARGET",
            "default_statistics_target": "R2R_POSTGRES_DEFAULT_STATISTICS_TARGET",
            "effective_cache_size": "R2R_POSTGRES_EFFECTIVE_CACHE_SIZE",
            "effective_io_concurrency": "R2R_POSTGRES_EFFECTIVE_IO_CONCURRENCY",
            "huge_pages": "R2R_POSTGRES_HUGE_PAGES",
            "maintenance_work_mem": "R2R_POSTGRES_MAINTENANCE_WORK_MEM",
            "min_wal_size": "R2R_POSTGRES_MIN_WAL_SIZE",
            "max_connections": "R2R_POSTGRES_MAX_CONNECTIONS",
            "max_parallel_workers_per_gather": "R2R_POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER",
            "max_parallel_workers": "R2R_POSTGRES_MAX_PARALLEL_WORKERS",
            "max_parallel_maintenance_workers": "R2R_POSTGRES_MAX_PARALLEL_MAINTENANCE_WORKERS",
            "max_wal_size": "R2R_POSTGRES_MAX_WAL_SIZE",
            "max_worker_processes": "R2R_POSTGRES_MAX_WORKER_PROCESSES",
            "random_page_cost": "R2R_POSTGRES_RANDOM_PAGE_COST",
            "statement_cache_size": "R2R_POSTGRES_STATEMENT_CACHE_SIZE",
            "shared_buffers": "R2R_POSTGRES_SHARED_BUFFERS",
            "wal_buffers": "R2R_POSTGRES_WAL_BUFFERS",
            "work_mem": "R2R_POSTGRES_WORK_MEM",
        }

        for setting, env_var in env_mapping.items():
            value = getattr(
                config.postgres_configuration_settings, setting, None
            )
            if value is None:
                value = os.getenv(env_var)

            if value is not None:
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
