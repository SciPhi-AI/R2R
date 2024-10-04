# TODO: Clean this up and make it more congruent across the vector database and the relational database.

import logging
import os
from typing import Optional

from core.base import (
    CryptoProvider,
    DatabaseConfig,
    DatabaseProvider,
    PostgresConfigurationSettings,
    RelationalDBProvider,
    VectorDBProvider,
)

from .relational import PostgresRelationalDBProvider
from .vector import PostgresVectorDBProvider

logger = logging.getLogger(__name__)


class PostgresDBProvider(DatabaseProvider):
    def __init__(
        self,
        config: DatabaseConfig,
        dimension: int,
        crypto_provider: CryptoProvider,
        user: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db_name: Optional[str] = None,
        project_name: Optional[str] = None,
        *args,
        **kwargs,
    ):
        super().__init__(config)

        user = config.user or os.getenv("POSTGRES_USER")
        if not user:
            raise ValueError(
                "Error, please set a valid POSTGRES_USER environment variable or set a 'user' in the 'database' settings of your `r2r.toml`."
            )
        self.user = user

        password = config.password or os.getenv("POSTGRES_PASSWORD")
        if not password:
            raise ValueError(
                "Error, please set a valid POSTGRES_PASSWORD environment variable or set a 'password' in the 'database' settings of your `r2r.toml`."
            )
        self.password = password

        host = config.host or os.getenv("POSTGRES_HOST")
        if not host:
            raise ValueError(
                "Error, please set a valid POSTGRES_HOST environment variable or set a 'host' in the 'database' settings of your `r2r.toml`."
            )
        self.host = host

        port = config.port or os.getenv("POSTGRES_PORT")  # type: ignore
        if not port:
            raise ValueError(
                "Error, please set a valid POSTGRES_PORT environment variable or set a 'port' in the 'database' settings of your `r2r.toml`."
            )
        self.port = port

        db_name = config.db_name or os.getenv("POSTGRES_DBNAME")
        if not db_name:
            raise ValueError(
                "Error, please set a valid POSTGRES_DBNAME environment variable or set a 'db_name' in the 'database' settings of your `r2r.toml`."
            )
        self.db_name = db_name

        project_name = (
            config.app.project_name
            or os.getenv("R2R_PROJECT_NAME")
            # Remove the following line after deprecation
            or os.getenv("POSTGRES_PROJECT_NAME")
        )
        if not project_name:
            raise ValueError(
                "Error, please set a valid R2R_PROJECT_NAME environment variable or set a 'project_name' in the 'database' settings of your `r2r.toml`."
            )
        self.project_name = project_name

        if not all([user, password, host, port, db_name, project_name]):
            raise ValueError(
                "Error, please set the POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DBNAME, and `R2R_PROJECT_NAME` environment variables to use pgvector database."
            )

        # Check if it's a Unix socket connection
        if host.startswith("/") and not port:
            self.connection_string = (
                f"postgresql://{user}:{password}@/{db_name}?host={host}"
            )
            logger.info("Connecting to Postgres via Unix socket")
        else:
            self.connection_string = (
                f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
            )
            logger.info("Connecting to Postgres via TCP/IP")

        self.vector_db_dimension = dimension
        self.project_name = project_name
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

    def _get_table_name(self, base_name: str) -> str:
        return f"{self.project_name}.{base_name}"

    async def initialize(self):
        self.vector = self._initialize_vector_db()
        self.relational = await self._initialize_relational_db()

    def _initialize_vector_db(self) -> VectorDBProvider:
        return PostgresVectorDBProvider(
            self.config,
            connection_string=self.connection_string,
            project_name=self.project_name,
            dimension=self.vector_db_dimension,
        )

    async def _initialize_relational_db(self) -> RelationalDBProvider:
        relational_db = PostgresRelationalDBProvider(
            self.config,
            connection_string=self.connection_string,
            crypto_provider=self.crypto_provider,
            project_name=self.project_name,
            postgres_configuration_settings=self.postgres_configuration_settings,
        )
        await relational_db.initialize()
        return relational_db

    def _get_postgres_configuration_settings(
        self, config: DatabaseConfig
    ) -> PostgresConfigurationSettings:
        settings = PostgresConfigurationSettings()

        env_mapping = {
            "max_connections": "POSTGRES_MAX_CONNECTIONS",
            "shared_buffers": "POSTGRES_SHARED_BUFFERS",
            "effective_cache_size": "POSTGRES_EFFECTIVE_CACHE_SIZE",
            "maintenance_work_mem": "POSTGRES_MAINTENANCE_WORK_MEM",
            "checkpoint_completion_target": "POSTGRES_CHECKPOINT_COMPLETION_TARGET",
            "wal_buffers": "POSTGRES_WAL_BUFFERS",
            "default_statistics_target": "POSTGRES_DEFAULT_STATISTICS_TARGET",
            "random_page_cost": "POSTGRES_RANDOM_PAGE_COST",
            "effective_io_concurrency": "POSTGRES_EFFECTIVE_IO_CONCURRENCY",
            "work_mem": "POSTGRES_WORK_MEM",
            "huge_pages": "POSTGRES_HUGE_PAGES",
            "min_wal_size": "POSTGRES_MIN_WAL_SIZE",
            "max_wal_size": "POSTGRES_MAX_WAL_SIZE",
            "max_worker_processes": "POSTGRES_MAX_WORKER_PROCESSES",
            "max_parallel_workers_per_gather": "POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER",
            "max_parallel_workers": "POSTGRES_MAX_PARALLEL_WORKERS",
            "max_parallel_maintenance_workers": "POSTGRES_MAX_PARALLEL_MAINTENANCE_WORKERS",
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
