import logging
import os
from typing import Optional, Union

from r2r.core import VectorDBProvider, VectorEntry, VectorSearchResult

logger = logging.getLogger(__name__)


class QdrantDB(VectorDBProvider):
    def __init__(self, provider: str = "qdrant") -> None:
        logger.info(
            "Initializing `QdrantDB` to store and retrieve embeddings."
        )

        super().__init__(provider)
        if provider != "qdrant":
            raise ValueError(
                "QdrantDB must be initialized with provider `qdrant`."
            )
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models

            self.models = models
        except ImportError:
            raise ValueError(
                f"Error, `qdrant_client` is not installed. Please install it using `pip install qdrant-client`."
            )
        try:
            host = os.getenv("QDRANT_HOST")
            port = os.getenv("QDRANT_PORT")
            api_key = os.getenv("QDRANT_API_KEY")

            if not host or not port or not api_key:
                raise ValueError(
                    "Error, QdrantDB requires the QDRANT_HOST, QDRANT_PORT, and QDRANT_API_KEY environment variables."
                )

            self.client = QdrantClient(host, port=int(port), api_key=api_key)
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to the qdrant provider."
            )
        self.collection_name: Optional[str] = None

    def initialize_collection(
        self, collection_name: str, dimension: int
    ) -> None:
        self.collection_name = collection_name
        try:
            result = self.client.create_collection(
                collection_name=f"{collection_name}",
                vectors_config=self.models.VectorParams(
                    size=dimension, distance=self.models.Distance.COSINE
                ),
            )
            if result is False:
                raise ValueError(
                    f"Error occurred while attempting to create collection {collection_name}."
                )
        except Exception:
            # TODO - Handle more appropriately - create collection fails when it already exists
            pass

    def copy(self, entry: VectorEntry, commit=True) -> None:
        raise NotImplementedError(
            "QdrantDB does not support the `copy` method."
        )

    def upsert(self, entry: VectorEntry, commit=True) -> None:
        if self.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )
        points = [
            self.models.PointStruct(
                id=str(entry.id),
                vector=list([float(ele) for ele in entry.vector]),
                payload=entry.metadata,
            )
        ]
        self.client.upsert(
            collection_name=f"{self.collection_name}",
            points=points,
        )

    def upsert_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        if self.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert_entries`."
            )
        points = [
            self.models.PointStruct(
                id=str(entry.id),
                vector=list([float(ele) for ele in entry.vector]),
                payload=entry.metadata,
            )
            for entry in entries
        ]
        self.client.upsert(
            collection_name=f"{self.collection_name}",
            points=points,
        )

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Union[bool, int, str]] = {},
        limit: int = 10,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        if self.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `search`."
            )

        results = self.client.search(
            collection_name=f"{self.collection_name}",
            query_filter=self.models.Filter(
                must=[
                    self.models.FieldCondition(
                        key=key,
                        match=self.models.MatchValue(
                            value=value,
                        ),
                    )
                    for key, value in filters.items()
                ]
            ),
            query_vector=query_vector,
            limit=limit,
        )

        return [
            VectorSearchResult(
                str(result.id), result.score, result.payload or {}
            )
            for result in results
        ]

    def create_index(self, index_type, column_name, index_options):
        pass

    def close(self):
        pass

    def filtered_deletion(
        self, key: str, value: Union[bool, int, str]
    ) -> None:
        if self.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `filtered_deletion`."
            )

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=self.models.FilterSelector(
                filter=self.models.Filter(
                    must=[
                        self.models.FieldCondition(
                            key=key,
                            match=self.models.MatchValue(value=value),
                        ),
                    ],
                )
            ),
        )
        return

    def get_all_unique_values(
        self, collection_name: str, metadata_field: str, filters: dict = {}
    ) -> list:
        if self.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `get_all_unique_values`."
            )

        # Create a scroll filter based on the provided filters
        scroll_filter = None
        if filters:
            filter_conditions = [
                self.models.FieldCondition(
                    key=key, match=self.models.MatchValue(value=value)
                )
                for key, value in filters.items()
            ]
            scroll_filter = self.models.Filter(must=filter_conditions)

        unique_values = set()

        # Scroll through the collection and retrieve points in batches
        next_page_offset = None
        while True:
            records, next_page_offset = self.scroll(
                collection_name=collection_name,
                scroll_filter=scroll_filter,
                offset=next_page_offset,
                limit=100,  # Adjust the batch size as needed
                with_payload=True,
            )

            for record in records:
                if metadata_field in record.payload:
                    unique_values.add(record.payload[metadata_field])

            if next_page_offset is None:
                break

        return list(unique_values)
