import logging
import os
from typing import Optional, Union

from r2r.core import (
    SearchResult,
    VectorDBConfig,
    VectorDBProvider,
    VectorEntry,
)

logger = logging.getLogger(__name__)


class QdrantDB(VectorDBProvider):
    def __init__(self, config: VectorDBConfig) -> None:
        logger.info(
            "Initializing `QdrantDB` to store and retrieve embeddings."
        )

        super().__init__(config)
        if config.provider != "qdrant":
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

    def initialize_collection(self, dimension: int) -> None:
        try:
            result = self.client.create_collection(
                collection_name=f"{self.config.collection_name}",
                vectors_config=self.models.VectorParams(
                    size=dimension, distance=self.models.Distance.COSINE
                ),
            )
            if result is False:
                raise ValueError(
                    f"Error occurred while attempting to create collection {self.config.collection_name}."
                )
        except Exception:
            # TODO - Handle more appropriately - create collection fails when it already exists
            pass

    def copy(self, entry: VectorEntry, commit=True) -> None:
        raise NotImplementedError(
            "QdrantDB does not support the `copy` method."
        )

    def upsert(self, entry: VectorEntry, commit=True) -> None:
        if self.config.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )
        points = [
            self.models.PointStruct(
                id=str(entry.id),
                vector=list([float(ele) for ele in entry.vector.data]),
                payload=entry.metadata,
            )
        ]
        self.client.upsert(
            collection_name=f"{self.config.collection_name}",
            points=points,
        )

    def upsert_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        if self.config.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert_entries`."
            )
        points = [
            self.models.PointStruct(
                id=str(entry.id),
                vector=list([float(ele) for ele in entry.vector.data]),
                payload=entry.metadata,
            )
            for entry in entries
        ]
        self.client.upsert(
            collection_name=f"{self.config.collection_name}",
            points=points,
        )

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Union[bool, int, str]] = {},
        limit: int = 10,
        *args,
        **kwargs,
    ) -> list[SearchResult]:
        if self.config.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `search`."
            )

        results = self.client.search(
            collection_name=f"{self.config.collection_name}",
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
            SearchResult(
                id=result.id, score=result.score, metadata=result.payload or {}
            )
            for result in results
        ]

    def create_index(self, index_type, column_name, index_options):
        pass

    def delete_by_metadata(
        self, metadata_field: str, metadata_value: Union[bool, int, str]
    ) -> None:
        if self.config.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `delete_by_metadata`."
            )

        self.client.delete(
            collection_name=self.config.collection_name,
            points_selector=self.models.FilterSelector(
                filter=self.models.Filter(
                    must=[
                        self.models.FieldCondition(
                            key=metadata_field,
                            match=self.models.MatchValue(value=metadata_value),
                        ),
                    ],
                )
            ),
        )
        return

    def get_metadatas(
        self,
        metadata_fields: list[str],
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> list[dict]:
        if self.config.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `get_metadatas`."
            )

        # Create a scroll filter based on the provided filter field and value
        scroll_filter = None
        if filter_field and filter_value:
            scroll_filter = self.models.Filter(
                must=[
                    self.models.FieldCondition(
                        key=filter_field,
                        match=self.models.MatchValue(value=filter_value),
                    )
                ]
            )

        unique_values = {}

        # Scroll through the collection and retrieve points in batches
        next_page_offset = None
        while True:
            records, next_page_offset = self.client.scroll(
                collection_name=self.config.collection_name,
                scroll_filter=scroll_filter,
                offset=next_page_offset,
                limit=100,  # Adjust the batch size as needed
                with_payload=True,
            )

            for record in records:
                metadata = record.payload
                if all(field in metadata for field in metadata_fields):
                    key = tuple(metadata[field] for field in metadata_fields)
                    if key not in unique_values:
                        unique_values[key] = {}
                    for field in metadata_fields:
                        unique_values[key][field] = metadata[field]

            if next_page_offset is None:
                break

        return list(unique_values.values())
