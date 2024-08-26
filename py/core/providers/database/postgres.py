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
from .vecs import Client, create_client
from .vector import PostgresVectorDBProvider

logger = logging.getLogger(__name__)


class PostgresDBProvider(DatabaseProvider):
    def __init__(
        self,
        config: DatabaseConfig,
        dimension: int,
        crypto_provider: Optional[CryptoProvider] = None,
        *args,
        **kwargs,
    ):
        user = config.extra_fields.get("user", None) or os.getenv(
            "POSTGRES_USER"
        )
        if not user:
            raise ValueError(
                "Error, please set a valid POSTGRES_USER environment variable or set a 'user' in the 'database' settings of your `r2r.toml`."
            )
        password = config.extra_fields.get("password", None) or os.getenv(
            "POSTGRES_PASSWORD"
        )
        if not password:
            raise ValueError(
                "Error, please set a valid POSTGRES_PASSWORD environment variable or set a 'password' in the 'database' settings of your `r2r.toml`."
            )

        host = config.extra_fields.get("host", None) or os.getenv(
            "POSTGRES_HOST"
        )
        if not host:
            raise ValueError(
                "Error, please set a valid POSTGRES_HOST environment variable or set a 'host' in the 'database' settings of your `r2r.toml`."
            )

        port = config.extra_fields.get("port", None) or os.getenv(
            "POSTGRES_PORT"
        )
        if not port:
            raise ValueError(
                "Error, please set a valid POSTGRES_PORT environment variable or set a 'port' in the 'database' settings of your `r2r.toml`."
            )

        db_name = config.extra_fields.get("db_name", None) or os.getenv(
            "POSTGRES_DBNAME"
        )
        if not db_name:
            raise ValueError(
                "Error, please set a valid POSTGRES_DBNAME environment variable or set a 'db_name' in the 'database' settings of your `r2r.toml`."
            )

        collection_name = config.extra_fields.get(
            "vecs_collection", None
        ) or os.getenv("POSTGRES_VECS_COLLECTION")
        if not collection_name:
            raise ValueError(
                "Error, please set a valid POSTGRES_VECS_COLLECTION environment variable or set a 'vecs_collection' in the 'database' settings of your `r2r.toml`."
            )

        if not all([user, password, host, port, db_name, collection_name]):
            raise ValueError(
                "Error, please set the POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DBNAME, and POSTGRES_VECS_COLLECTION environment variables to use pgvector database."
            )
        try:
            DB_CONNECTION = (
                f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
            )
            self.vx: Client = create_client(DB_CONNECTION)
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to the pgvector provider with {DB_CONNECTION}."
            )
        self.vector_db_dimension = dimension
        self.collection_name = collection_name
        self.config: DatabaseConfig = config
        self.crypto_provider = crypto_provider
        super().__init__(config)

    def _initialize_vector_db(self) -> VectorDBProvider:
        return PostgresVectorDBProvider(
            self.config,
            vx=self.vx,
            collection_name=self.collection_name,
            dimension=self.vector_db_dimension,
        )

    def _initialize_relational_db(self) -> RelationalDBProvider:
        provider = PostgresRelationalDBProvider(
            self.config,
            vx=self.vx,
            crypto_provider=self.crypto_provider,
            collection_name=self.collection_name,
        )
        return provider
