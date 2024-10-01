"""
Defines the 'Client' class

Importing from the `vecs.client` directly is not supported.
All public classes, enums, and functions are re-exported by the top level `vecs` module.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy
from deprecated import deprecated
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from .adapter import Adapter
from .exc import CollectionNotFound

if TYPE_CHECKING:
    from core.providers.database.vecs.collection import Collection

logger = logging.getLogger(__name__)


class Client:
    """
    The `vecs.Client` class serves as an interface to a PostgreSQL database with pgvector support. It facilitates
    the creation, retrieval, listing and deletion of vector collections, while managing connections to the
    database.

    A `Client` instance represents a connection to a PostgreSQL database. This connection can be used to create
    and manipulate vector collections, where each collection is a group of vector records in a PostgreSQL table.

    The `vecs.Client` class can be also supports usage as a context manager to ensure the connection to the database
    is properly closed after operations, or used directly.

    Example usage:

        DB_CONNECTION = "postgresql://<user>:<password>@<host>:<port>/<db_name>"

        with vecs.create_client(DB_CONNECTION) as vx:
            # do some work
            pass

        # OR

        vx = vecs.create_client(DB_CONNECTION)
        # do some work
        vx.disconnect()
    """

    def __init__(
        self,
        connection_string: str,
        pool_size: int = 1,
        max_retries: int = 3,
        retry_delay: int = 1,
        project_name: str = "vecs",
    ):
        self.engine = create_engine(
            connection_string,
            pool_size=pool_size,
            poolclass=QueuePool,
            pool_recycle=300,  # Recycle connections after 5 min
        )
        self.meta = MetaData(schema=project_name)
        self.Session = sessionmaker(self.engine)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.project_name = project_name
        self.vector_version: Optional[str] = None
        self._initialize_database()

    def _initialize_database(self):
        retries = 0
        error = None
        while retries < self.max_retries:
            try:
                with self.Session() as sess:
                    with sess.begin():
                        self._create_schema(sess)
                        self._create_extension(sess)
                        self._get_vector_version(sess)
                return
            except Exception as e:
                logger.warning(
                    f"Database connection error: {str(e)}. Retrying in {self.retry_delay} seconds..."
                )
                retries += 1
                time.sleep(self.retry_delay)
                error = e

        error_message = f"Failed to initialize database after {self.max_retries} retries with error: {str(error)}"
        logger.error(error_message)
        raise RuntimeError(error_message)

    def _create_schema(self, sess):
        try:
            sess.execute(
                text(f'CREATE SCHEMA IF NOT EXISTS "{self.project_name}";')
            )
        except Exception as e:
            logger.warning(f"Failed to create schema: {str(e)}")

    def _create_extension(self, sess):
        try:
            sess.execute(text(f"CREATE EXTENSION IF NOT EXISTS vector;"))
            sess.execute(text(f"CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            sess.execute(
                text(f"CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;")
            )
        except Exception as e:
            logger.warning(f"Failed to create extension: {str(e)}")

    def _get_vector_version(self, sess):
        try:
            self.vector_version = sess.execute(
                text(
                    "SELECT installed_version FROM pg_available_extensions WHERE name = 'vector' LIMIT 1;"
                )
            ).scalar_one()
        except sqlalchemy.exc.InternalError as e:
            logger.error(f"Failed with internal alchemy error: {str(e)}")

            import psycopg2

            if isinstance(e.orig, psycopg2.errors.InFailedSqlTransaction):
                sess.rollback()
                self.vector_version = sess.execute(
                    text(
                        "SELECT installed_version FROM pg_available_extensions WHERE name = 'vector' LIMIT 1;"
                    )
                ).scalar_one()
            else:
                raise e
        except Exception as e:
            logger.error(f"Failed to retrieve vector version: {str(e)}")
            raise e

    def _supports_hnsw(self):
        return (
            not self.vector_version.startswith("0.4")
            and not self.vector_version.startswith("0.3")
            and not self.vector_version.startswith("0.2")
            and not self.vector_version.startswith("0.1")
            and not self.vector_version.startswith("0.0")
        )

    def get_or_create_vector_table(
        self,
        name: str,
        *,
        dimension: Optional[int] = None,
        adapter: Optional[Adapter] = None,
    ) -> Collection:
        """
        Get a vector collection by name, or create it if no collection with
        *name* exists.

        Args:
            name (str): The name of the collection.

        Keyword Args:
            dimension (int): The dimensionality of the vectors in the collection.
            pipeline (int): The dimensionality of the vectors in the collection.

        Returns:
            Collection: The created collection.

        Raises:
            CollectionAlreadyExists: If a collection with the same name already exists
        """
        from core.providers.database.vecs.collection import Collection

        adapter_dimension = adapter.exported_dimension if adapter else None

        collection = Collection(
            name=name,
            dimension=dimension or adapter_dimension,  # type: ignore
            client=self,
            adapter=adapter,
        )

        return collection._create_if_not_exists()

    @deprecated("use Client.get_or_create_vector_table")
    def create_collection(self, name: str, dimension: int) -> Collection:
        """
        Create a new vector collection.

        Args:
            name (str): The name of the collection.
            dimension (int): The dimensionality of the vectors in the collection.

        Returns:
            Collection: The created collection.

        Raises:
            CollectionAlreadyExists: If a collection with the same name already exists
        """
        from core.providers.database.vecs.collection import Collection

        return Collection(name, dimension, self)._create()

    @deprecated("use Client.get_or_create_vector_table")
    def get_collection(self, name: str) -> Collection:
        """
        Retrieve an existing vector collection.

        Args:
            name (str): The name of the collection.

        Returns:
            Collection: The retrieved collection.

        Raises:
            CollectionNotFound: If no collection with the given name exists.
        """
        from core.providers.database.vecs.collection import Collection

        query = text(
            f"""
        select
            relname as table_name,
            atttypmod as embedding_dim
        from
            pg_class pc
            join pg_attribute pa
                on pc.oid = pa.attrelid
        where
            pc.relnamespace = "{self.project_name}"::regnamespace
            and pc.relkind = 'r'
            and pa.attname = 'vec'
            and not pc.relname ^@ '_'
            and pc.relname = :name
        """
        ).bindparams(name=name)
        with self.Session() as sess:
            query_result = sess.execute(query).fetchone()

            if query_result is None:
                raise CollectionNotFound(
                    "No collection found with requested name"
                )

            name, dimension = query_result
            return Collection(
                name,
                dimension,
                self,
            )

    def list_collections(self) -> List["Collection"]:
        """
        List all vector collections.

        Returns:
            list[Collection]: A list of all collections.
        """
        from core.providers.database.vecs.collection import Collection

        return Collection._list_collections(self)

    def delete_collection(self, name: str) -> None:
        """
        Delete a vector collection.

        If no collection with requested name exists, does nothing.

        Args:
            name (str): The name of the collection.

        Returns:
            None
        """
        from core.providers.database.vecs.collection import Collection

        Collection(name, -1, self)._drop()
        return

    def disconnect(self) -> None:
        """
        Disconnect the client from the database.

        Returns:
            None
        """
        self.engine.dispose()
        logger.info("Disconnected from the database.")
        return

    def __enter__(self) -> "Client":
        """
        Enable use of the 'with' statement.

        Returns:
            Client: The current instance of the Client.
        """

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Disconnect the client on exiting the 'with' statement context.

        Args:
            exc_type: The exception type, if any.
            exc_val: The exception value, if any.
            exc_tb: The traceback, if any.

        Returns:
            None
        """
        self.disconnect()
        return
