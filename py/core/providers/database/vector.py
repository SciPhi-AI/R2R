import concurrent.futures
import copy
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.exc import NoResultFound, SQLAlchemyError

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
        self.project_name = kwargs.get("project_name", None)
        connection_string = kwargs.get("connection_string", None)
        if not connection_string:
            raise ValueError(
                "Please provide a valid `connection_string` to the `PostgresVectorDBProvider`."
            )
        self.vx: Client = create_client(
            connection_string=connection_string, project_name=self.project_name
        )
        if not self.vx:
            raise ValueError(
                "Error occurred while attempting to connect to the pgvector provider."
            )
        self.project_name = kwargs.get("project_name", None)
        if not self.project_name:
            raise ValueError(
                "Please provide a valid `project_name` to the `PostgresVectorDBProvider`."
            )
        dimension = kwargs.get("dimension", None)
        if not dimension:
            raise ValueError(
                "Please provide a valid `dimension` to the `PostgresVectorDBProvider`."
            )

        self._initialize_vector_db(dimension)
        logger.info(
            f"Successfully initialized PGVectorDB for project: {self.project_name}"
        )

    def _initialize_vector_db(self, dimension: int) -> None:
        # Create extension for trigram similarity
        with self.vx.Session() as sess:
            sess.execute(text(f"CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
            sess.execute(text(f"CREATE EXTENSION IF NOT EXISTS btree_gin;"))
            sess.commit()

        self.collection = self.vx.get_or_create_vector_table(
            name=self.project_name, dimension=dimension
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
                extraction_id=result[0],  # type: ignore
                document_id=result[1],  # type: ignore
                user_id=result[2],  # type: ignore
                collection_ids=result[3],  # type: ignore
                text=result[4],  # type: ignore
                score=1 - float(result[5]),  # type: ignore
                metadata=result[6],  # type: ignore
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
        return self.collection.full_text_search(
            query_text=query_text, search_settings=search_settings
        )

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

        semantic_settings = copy.deepcopy(search_settings)
        semantic_settings.search_limit += search_settings.offset

        full_text_settings = copy.deepcopy(search_settings)
        full_text_settings.hybrid_search_settings.full_text_limit += (  # type: ignore
            search_settings.offset
        )

        # Use ThreadPoolExecutor to run searches in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            semantic_future = executor.submit(
                self.semantic_search, query_vector, semantic_settings
            )
            full_text_future = executor.submit(
                self.full_text_search, query_text, full_text_settings
            )

            # Wait for both searches to complete
            concurrent.futures.wait([semantic_future, full_text_future])

        semantic_results: list[VectorSearchResult] = semantic_future.result()
        full_text_results: list[VectorSearchResult] = full_text_future.result()

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
            result.extraction_id: {
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
            result.extraction_id: {
                "semantic_rank": rank,
                "full_text_rank": full_text_limit,
                "data": result,
            }
            for rank, result in enumerate(semantic_results, 1)
        }

        for rank, result in enumerate(full_text_results, 1):
            if result.extraction_id in combined_results:
                combined_results[result.extraction_id]["full_text_rank"] = rank
            else:
                combined_results[result.extraction_id] = {
                    "semantic_rank": semantic_limit,
                    "full_text_rank": rank,
                    "data": result,
                }

        # Filter out non-overlapping results
        combined_results = {
            k: v
            for k, v in combined_results.items()
            if v["semantic_rank"] <= semantic_limit * 2  # type: ignore
            and v["full_text_rank"] <= full_text_limit * 2  # type: ignore
        }

        # Calculate RRF scores
        for result in combined_results.values():  # type: ignore
            semantic_score = 1 / (rrf_k + result["semantic_rank"])  # type: ignore
            full_text_score = 1 / (rrf_k + result["full_text_rank"])  # type: ignore
            result["rrf_score"] = (  # type: ignore
                semantic_score * semantic_weight
                + full_text_score * full_text_weight
            ) / (semantic_weight + full_text_weight)

        # Sort by RRF score and apply offset and limit
        sorted_results = sorted(
            combined_results.values(),
            key=lambda x: x["rrf_score"],  # type: ignore
            reverse=True,
        )
        offset_results = sorted_results[
            search_settings.offset : search_settings.offset
            + search_settings.search_limit
        ]

        return [
            VectorSearchResult(
                extraction_id=result["data"].extraction_id,  # type: ignore
                document_id=result["data"].document_id,  # type: ignore
                user_id=result["data"].user_id,  # type: ignore
                collection_ids=result["data"].collection_ids,  # type: ignore
                text=result["data"].text,  # type: ignore
                score=result["rrf_score"],  # type: ignore
                metadata={
                    **result["data"].metadata,  # type: ignore
                    "semantic_rank": result["semantic_rank"],
                    "full_text_rank": result["full_text_rank"],
                },
            )
            for result in offset_results
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
    ) -> dict[str, dict[str, str]]:
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
            UPDATE {self.project_name}."{table_name}"
            SET collection_ids = array_append(collection_ids, :collection_id)
            WHERE document_id = :document_id AND NOT (:collection_id = ANY(collection_ids))
            RETURNING document_id
            """
        )

        with self.vx.Session() as sess:
            result = sess.execute(
                query,
                {"document_id": document_id, "collection_id": collection_id},
            ).fetchone()
            sess.commit()

        if not result:
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
            UPDATE {self.project_name}."{table_name}"
            SET collection_ids = array_remove(collection_ids, :collection_id)
            WHERE document_id = :document_id AND :collection_id = ANY(collection_ids)
            RETURNING document_id
            """
        )

        with self.vx.Session() as sess:
            result = sess.execute(
                query,
                {"document_id": document_id, "collection_id": collection_id},
            ).fetchone()
            sess.commit()

        if not result:
            logger.warning(
                f"Document {document_id} not found in collection {collection_id} or already removed"
            )

    def remove_collection_from_documents(self, collection_id: str) -> None:
        if self.collection is None:
            raise ValueError("Collection is not initialized.")

        table_name = self.collection.table.name
        query = text(
            f"""
            UPDATE {self.project_name}."{table_name}"
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
            UPDATE {self.project_name}."{table_name}"
            SET user_id = NULL
            WHERE user_id = :user_id
            """
        )

        with self.vx.Session() as sess:
            sess.execute(query, {"user_id": user_id})
            sess.commit()

    def delete_collection(self, collection_id: str) -> None:
        if self.collection is None:
            raise ValueError("Collection is not initialized.")

        table_name = self.collection.table.name

        query = text(
            f"""
            WITH updated AS (
                UPDATE {self.project_name}."{table_name}"
                SET collection_ids = array_remove(collection_ids, :collection_id)
                WHERE :collection_id = ANY(collection_ids)
                RETURNING 1
            )
            SELECT COUNT(*) AS affected_rows FROM updated
            """
        )

        with self.vx.Session() as sess:
            try:
                result = sess.execute(query, {"collection_id": collection_id})
                row = result.one()
                affected_rows = row.affected_rows
                sess.commit()

                if affected_rows == 0:
                    raise ValueError(
                        f"Collection {collection_id} not found in any documents."
                    )
            except NoResultFound:
                raise ValueError(
                    f"Unexpected error: No result returned for collection {collection_id}"
                )
            except SQLAlchemyError as e:
                sess.rollback()
                logger.error(
                    f"Error deleting collection {collection_id}: {str(e)}"
                )
                raise

    def get_document_chunks(
        self, document_id: str, offset: int = 0, limit: int = -1
    ) -> dict[str, Any]:
        if not self.collection:
            raise ValueError("Collection is not initialized.")

        limit_clause = f"LIMIT {limit}" if limit != -1 else ""
        table_name = self.collection.table.name
        query = text(
            f"""
            SELECT extraction_id, document_id, user_id, collection_ids, text, metadata, COUNT(*) OVER() AS total
            FROM {self.project_name}."{table_name}"
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

        chunks = []
        total = 0

        if results:
            total = results[0][6]
            chunks = [
                {
                    "extraction_id": result[0],
                    "document_id": result[1],
                    "user_id": result[2],
                    "collection_ids": result[3],
                    "text": result[4],
                    "metadata": result[5],
                }
                for result in results
            ]

        return {"results": chunks, "total_entries": total}

    def close(self) -> None:
        if self.vx:
            with self.vx.Session() as sess:
                sess.close()
                if sess.bind:
                    sess.bind.dispose()  # type: ignore

        logger.info("Closed PGVectorDB connection.")
