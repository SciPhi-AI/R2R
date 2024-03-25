import logging
import os
from typing import Optional, Union

from r2r.core import VectorDBProvider, VectorEntry, VectorSearchResult
from r2r.vecs.client import Client
from r2r.vecs.collection import Collection

logger = logging.getLogger(__name__)


class PGVectorDB(VectorDBProvider):
    def __init__(self, provider: str = "pgvector") -> None:
        logger.info(
            "Initializing `PGVectorDB` to store and retrieve embeddings."
        )

        super().__init__(provider)
        if provider != "pgvector":
            raise ValueError(
                "PGVectorDB must be initialized with provider `pgvector`."
            )
        try:
            import r2r.vecs
        except ImportError:
            raise ValueError(
                f"Error, PGVectorDB requires the vecs library. Please run `poetry add vecs`."
            )
        try:
            user = os.getenv("POSTGRES_USER")
            password = os.getenv("POSTGRES_PASSWORD")
            host = os.getenv("POSTGRES_HOST")
            port = os.getenv("POSTGRES_PORT")
            db_name = os.getenv("POSTGRES_DBNAME")

            DB_CONNECTION = (
                f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
            )
            self.vx: Client = r2r.vecs.create_client(DB_CONNECTION)
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to the pgvector provider with {DB_CONNECTION}."
            )
        self.collection: Optional[Collection] = None

    def initialize_collection(
        self, collection_name: str, dimension: int
    ) -> None:
        self.collection = self.vx.get_or_create_collection(
            name=collection_name, dimension=dimension
        )

    def copy(self, entry: VectorEntry, commit=True) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `copy`."
            )

        self.collection.copy(
            records=[(str(entry.id), entry.vector, entry.metadata)]
        )

    def copy_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `copy_entries`."
            )

        self.collection.copy(
            records=[
                (str(entry.id), entry.vector, entry.metadata)
                for entry in entries
            ]
        )

    def upsert(self, entry: VectorEntry, commit=True) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )

        self.collection.upsert(
            records=[(str(entry.id), entry.vector, entry.metadata)]
        )

    def upsert_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert_entries`."
            )

        self.collection.upsert(
            records=[
                (str(entry.id), entry.vector, entry.metadata)
                for entry in entries
            ]
        )

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Union[bool, int, str]] = {},
        limit: int = 10,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `search`."
            )
        measure = kwargs.get("measure", "cosine_distance")
        mapped_filters = {
            key: {"$eq": value} for key, value in filters.items()
        }

        return [
            VectorSearchResult(ele[0], 1 - ele[1], ele[2])  # type: ignore
            for ele in self.collection.query(
                data=query_vector,
                limit=limit,
                filters=mapped_filters,
                measure=measure,
                include_value=True,
                include_metadata=True,
            )
        ]

    def create_index(self, index_type, column_name, index_options):
        pass

    def close(self):
        pass

    def filtered_deletion(
        self, key: str, value: Union[bool, int, str]
    ) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `filtered_deletion`."
            )
        self.collection.delete(filters={key: {"$eq": value}})  # type: ignore

    def get_all_unique_values(
        self, metadata_field: str, filters: dict = {}
    ) -> list:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `get_all_unique_values`."
            )

        mapped_filters = {
            key: {"$eq": value} for key, value in filters.items()
        }

        # Pass an empty vector as the `data` argument
        records = self.collection.query(
            data=[0] * self.collection.dimension,  # Empty vector
            filters=mapped_filters,
            include_metadata=True,
            include_value=False,
            # Remove the `limit` argument to retrieve all records
        )

        unique_values = set(
            record[1].get(metadata_field) for record in records
        )

        return list(unique_values)
