import concurrent.futures
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from sqlalchemy import text

from core.base import (
    DatabaseConfig,
    VectorDBProvider,
    VectorEntry,
    VectorSearchResult,
)
from core.base.abstractions import VectorSearchSettings

from .vecs import (
    Client,
    Collection,
    IndexArgsHNSW,
    IndexMeasure,
    IndexMethod,
    create_client,
)

logger = logging.getLogger(__name__)


class PostgresVectorDBProvider(VectorDBProvider):
    def __init__(self, config: DatabaseConfig, *args, **kwargs):
        super().__init__(config)
        self.collection: Optional[Collection] = None
        connection_string = kwargs.get("connection_string", None)
        if not connection_string:
            raise ValueError(
                "Please provide a valid `connection_string` to the `PostgresVectorDBProvider`."
            )
        self.vx: Client = create_client(connection_string=connection_string)
        if not self.vx:
            raise ValueError(
                "Error occurred while attempting to connect to the pgvector provider."
            )
        self.collection_name = kwargs.get("collection_name", None)
        if not self.collection_name:
            raise ValueError(
                "Please provide a valid `collection_name` to the `PostgresVectorDBProvider`."
            )
        dimension = kwargs.get("dimension", None)
        if not dimension:
            raise ValueError(
                "Please provide a valid `dimension` to the `PostgresVectorDBProvider`."
            )

        self.collection: Optional[Collection] = None
        self._initialize_vector_db(dimension)
        logger.info(
            f"Successfully initialized PGVectorDB with collection: {self.collection_name}"
        )

    def _initialize_vector_db(self, dimension: int) -> None:
        # Create extension for trigram similarity
        with self.vx.Session() as sess:
            sess.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            sess.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gin;"))
            sess.commit()

        self.collection = self.vx.get_or_create_collection(
            name=self.collection_name, dimension=dimension
        )
        self.create_index()

    def upsert(self, entry: VectorEntry) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )

        self.collection.upsert(
            records=[
                (
                    entry.fragment_id,
                    entry.extraction_id,
                    entry.document_id,
                    entry.user_id,
                    entry.collection_ids,
                    entry.vector.data,
                    entry.text,
                    entry.metadata,
                )
            ]
        )

    def upsert_entries(self, entries: list[VectorEntry]) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert_entries`."
            )

        self.collection.upsert(
            records=[
                (
                    entry.fragment_id,
                    entry.extraction_id,
                    entry.document_id,
                    entry.user_id,
                    entry.collection_ids,
                    entry.vector.data,
                    entry.text,
                    entry.metadata,
                )
                for entry in entries
            ]
        )

    def semantic_search(
        self, query_vector: list[float], search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `semantic_search`."
            )
        results = self.collection.semantic_search(
            vector=query_vector, search_settings=search_settings
        )
        return [
            VectorSearchResult(
                fragment_id=result[0],
                extraction_id=result[1],
                document_id=result[2],
                user_id=result[3],
                collection_ids=result[4],
                text=result[5],
                score=1 - float(result[6]),
                metadata=result[7],
            )
            for result in results
        ]

    def full_text_search(
        self, query_text: str, search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `full_text_search`."
            )
        results = self.collection.full_text_search(
            query_text=query_text, search_settings=search_settings
        )
        return results

    def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        search_settings: VectorSearchSettings,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        if search_settings.hybrid_search_settings is None:
            raise ValueError(
                "Please provide a valid `hybrid_search_settings` in the `search_settings`."
            )
        if (
            search_settings.hybrid_search_settings.full_text_limit
            < search_settings.search_limit
        ):
            raise ValueError(
                "The `full_text_limit` must be greater than or equal to the `search_limit`."
            )

        # Use ThreadPoolExecutor to run searches in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            semantic_future = executor.submit(
                self.semantic_search, query_vector, search_settings
            )
            full_text_future = executor.submit(
                self.full_text_search, query_text, search_settings
            )

            # Wait for both searches to complete
            concurrent.futures.wait([semantic_future, full_text_future])

        semantic_results = semantic_future.result()
        full_text_results = full_text_future.result()

        semantic_limit = search_settings.search_limit
        full_text_limit = (
            search_settings.hybrid_search_settings.full_text_limit
        )
        semantic_weight = (
            search_settings.hybrid_search_settings.semantic_weight
        )
        full_text_weight = (
            search_settings.hybrid_search_settings.full_text_weight
        )
        rrf_k = search_settings.hybrid_search_settings.rrf_k

        # Combine results using RRF
        combined_results = {
            result.fragment_id: {
                "semantic_rank": rank,
                "full_text_rank": full_text_limit,
                "data": result,
            }
            for rank, result in enumerate(semantic_results, 1)
        }

        semantic_limit = search_settings.search_limit
        full_text_limit = (
            search_settings.hybrid_search_settings.full_text_limit
        )
        semantic_weight = (
            search_settings.hybrid_search_settings.semantic_weight
        )
        full_text_weight = (
            search_settings.hybrid_search_settings.full_text_weight
        )
        rrf_k = search_settings.hybrid_search_settings.rrf_k
        # Combine results using RRF
        combined_results = {
            result.fragment_id: {
                "semantic_rank": rank,
                "full_text_rank": full_text_limit,
                "data": result,
            }
            for rank, result in enumerate(semantic_results, 1)
        }

        for rank, result in enumerate(full_text_results, 1):
            if result.fragment_id in combined_results:
                combined_results[result.fragment_id]["full_text_rank"] = rank
            else:
                combined_results[result.fragment_id] = {
                    "semantic_rank": semantic_limit,
                    "full_text_rank": rank,
                    "data": result,
                }

        # Filter out non-overlapping results
        combined_results = {
            k: v
            for k, v in combined_results.items()
            if v["semantic_rank"] <= semantic_limit * 2
            and v["full_text_rank"] <= full_text_limit * 2
        }

        # Calculate RRF scores
        for result in combined_results.values():
            semantic_score = 1 / (rrf_k + result["semantic_rank"])
            full_text_score = 1 / (rrf_k + result["full_text_rank"])
            result["rrf_score"] = (
                semantic_score * semantic_weight
                + full_text_score * full_text_weight
            ) / (semantic_weight + full_text_weight)

        # Sort by RRF score and convert to VectorSearchResult
        limit = min(semantic_limit, full_text_limit)
        sorted_results = sorted(
            combined_results.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )[:limit]

        return [
            VectorSearchResult(
                fragment_id=result["data"].fragment_id,
                extraction_id=result["data"].extraction_id,
                document_id=result["data"].document_id,
                user_id=result["data"].user_id,
                collection_ids=result["data"].collection_ids,
                text=result["data"].text,
                score=result["rrf_score"],
                metadata={
                    **result["data"].metadata,
                    "semantic_rank": result["semantic_rank"],
                    "full_text_rank": result["full_text_rank"],
                },
            )
            for result in sorted_results
        ]

    def create_index(
        self,
        index_type=IndexMethod.hnsw,
        measure=IndexMeasure.cosine_distance,
        index_options=None,
    ):
        if self.collection is None:
            raise ValueError("Collection is not initialized.")

        if index_options is None:
            index_options = IndexArgsHNSW(
                m=16, ef_construction=64
            )  # Default HNSW parameters

        self.collection.create_index(
            method=index_type,
            measure=measure,
            index_arguments=index_options,
            replace=True,
        )

    def delete(
        self,
        filters: dict[str, Any],
    ) -> list[str]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `delete`."
            )

        return self.collection.delete(filters=filters)

    def assign_document_to_collection(
        self, document_id: str, collection_id: str
    ) -> None:
        """
        Assign a document to a collection in the vector database.

        Args:
            document_id (str): The ID of the document to assign.
            collection_id (str): The ID of the collection to assign the document to.

        Raises:
            ValueError: If the collection is not initialized.
        """
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `assign_document_to_collection`."
            )

        table_name = self.collection.table.name
        query = text(
            f"""
            UPDATE vecs."{table_name}"
            SET collection_ids = array_append(collection_ids, :collection_id)
            WHERE document_id = :document_id AND NOT (:collection_id = ANY(collection_ids))
            RETURNING document_id
            """
        )

        with self.vx.Session() as sess:
            result = sess.execute(
                query,
                {"document_id": document_id, "collection_id": collection_id},
            )
            sess.commit()

        if result.rowcount == 0:
            logger.warning(
                f"Document {document_id} not found or already assigned to collection {collection_id}"
            )

    def remove_document_from_collection(
        self, document_id: str, collection_id: str
    ) -> None:
        """
        Remove a document from a collection in the vector database.

        Args:
            document_id (str): The ID of the document to remove.
            collection_id (str): The ID of the collection to remove the document from.

        Raises:
            ValueError: If the collection is not initialized.
        """
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `remove_document_from_collection`."
            )

        table_name = self.collection.table.name
        query = text(
            f"""
            UPDATE vecs."{table_name}"
            SET collection_ids = array_remove(collection_ids, :collection_id)
            WHERE document_id = :document_id AND :collection_id = ANY(collection_ids)
            RETURNING document_id
            """
        )

        with self.vx.Session() as sess:
            result = sess.execute(
                query,
                {"document_id": document_id, "collection_id": collection_id},
            )
            sess.commit()

        if result.rowcount == 0:
            logger.warning(
                f"Document {document_id} not found in collection {collection_id} or already removed"
            )

    def remove_collection_from_documents(self, collection_id: str) -> None:
        if self.collection is None:
            raise ValueError("Collection is not initialized.")

        table_name = self.collection.table.name
        query = text(
            f"""
            UPDATE vecs."{table_name}"
            SET collection_ids = array_remove(collection_ids, :collection_id)
            WHERE :collection_id = ANY(collection_ids)
            """
        )

        with self.vx.Session() as sess:
            sess.execute(query, {"collection_id": collection_id})
            sess.commit()

    def delete_user(self, user_id: str) -> None:
        if self.collection is None:
            raise ValueError("Collection is not initialized.")

        table_name = self.collection.table.name
        query = text(
            f"""
            UPDATE vecs."{table_name}"
            SET user_id = NULL
            WHERE user_id = :user_id
            """
        )

        with self.vx.Session() as sess:
            sess.execute(query, {"user_id": user_id})
            sess.commit()

    def delete_collection(self, collection_id: str) -> None:
        """
        Remove the specified collection ID from all documents in the vector database.

        Args:
            collection_id (str): The ID of the collection to remove from all documents.

        Raises:
            ValueError: If the collection is not initialized.
        """
        if self.collection is None:
            raise ValueError("Collection is not initialized.")

        table_name = self.collection.table.name
        query = text(
            f"""
            UPDATE vecs."{table_name}"
            SET collection_ids = array_remove(collection_ids, :collection_id)
            WHERE :collection_id = ANY(collection_ids)
            """
        )

        with self.vx.Session() as sess:
            result = sess.execute(query, {"collection_id": collection_id})
            sess.commit()

        affected_rows = result.rowcount
        logger.info(
            f"Removed collection {collection_id} from {affected_rows} documents."
        )

    def get_document_chunks(
        self, document_id: str, offset: int = 0, limit: int = -1
    ) -> dict:
        if not self.collection:
            raise ValueError("Collection is not initialized.")

        limit_clause = f"LIMIT {limit}" if limit != -1 else ""
        table_name = self.collection.table.name
        query = text(
            f"""
            SELECT fragment_id, extraction_id, document_id, user_id, collection_ids, text, metadata
            FROM vecs."{table_name}"
            WHERE document_id = :document_id
            ORDER BY CAST(metadata->>'chunk_order' AS INTEGER)
            {limit_clause} OFFSET :offset
        """
        )

        params = {"document_id": document_id, "offset": offset}
        if limit != -1:
            params["limit"] = limit

        with self.vx.Session() as sess:
            results = sess.execute(query, params).fetchall()

        return [
            {
                "fragment_id": result[0],
                "extraction_id": result[1],
                "document_id": result[2],
                "user_id": result[3],
                "collection_ids": result[4],
                "text": result[5],
                "metadata": result[6],
            }
            for result in results
        ]
