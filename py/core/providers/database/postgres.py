# TODO: Clean this up and make it more congruent across the vector database and the relational database.

import logging
import os
from typing import Optional

from core.base import (
    CryptoProvider,
    DatabaseConfig,
    DatabaseProvider,
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
            config.project_name
            or config.vecs_collection  # remove after deprecation
            or os.getenv("POSTGRES_PROJECT_NAME")
            or os.getenv(
                "POSTGRES_VECS_COLLECTION"
            )  # remove after deprecation
        )
        if not project_name:
            raise ValueError(
                "Error, please set a valid POSTGRES_PROJECT_NAME environment variable or set a 'project_name' in the 'database' settings of your `r2r.toml`."
            )
        self.project_name = project_name

        if not all([user, password, host, port, db_name, project_name]):
            raise ValueError(
                "Error, please set the POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DBNAME, and POSTGRES_PROJECT_NAME environment variables to use pgvector database."
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
        )
        await relational_db.initialize()
        return relational_db
