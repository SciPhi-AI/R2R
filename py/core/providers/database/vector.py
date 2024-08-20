import json
import logging
import os
import time
from typing import Any, Optional

from core.base import (
    DatabaseConfig,
    VectorDBProvider,
    VectorEntry,
    VectorSearchResult,
    generate_id_from_label,
)
from core.base.abstractions import VectorSearchSettings
from sqlalchemy import exc, text
from sqlalchemy.engine.url import make_url

from .vecs import Client, Collection, create_client

logger = logging.getLogger(__name__)


class PostgresVectorDBProvider(VectorDBProvider):
    def __init__(self, config: DatabaseConfig, *args, **kwargs):
        super().__init__(config)
        self.collection: Optional[Collection] = None
        self.vx: Client = kwargs.get("vx", None)
        if not self.vx:
            raise ValueError(
                "Please provide a valid `vx` client to the `PostgresVectorDBProvider`."
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

        # Check if a complete Postgres URI is provided
        postgres_uri = self.config.extra_fields.get(
            "postgres_uri"
        ) or os.getenv("POSTGRES_URI")

        if postgres_uri:
            # Log loudly that Postgres URI is being used
            logger.warning("=" * 50)
            logger.warning(
                "ATTENTION: Using provided Postgres URI for connection"
            )
            logger.warning("=" * 50)

            # Validate and use the provided URI
            try:
                parsed_uri = make_url(postgres_uri)
                if not all([parsed_uri.username, parsed_uri.database]):
                    raise ValueError(
                        "The provided Postgres URI is missing required components."
                    )
                DB_CONNECTION = postgres_uri

                # Log the sanitized URI (without password)
                sanitized_uri = parsed_uri.set(password="*****")
                logger.info(f"Connecting using URI: {sanitized_uri}")
            except Exception as e:
                raise ValueError(f"Invalid Postgres URI provided: {e}")
        else:
            # Fall back to existing logic for individual connection parameters
            user = self.config.extra_fields.get("user", None) or os.getenv(
                "POSTGRES_USER"
            )
            password = self.config.extra_fields.get(
                "password", None
            ) or os.getenv("POSTGRES_PASSWORD")
            host = self.config.extra_fields.get("host", None) or os.getenv(
                "POSTGRES_HOST"
            )
            port = self.config.extra_fields.get("port", None) or os.getenv(
                "POSTGRES_PORT"
            )
            db_name = self.config.extra_fields.get(
                "db_name", None
            ) or os.getenv("POSTGRES_DBNAME")

            if not all([user, password, host, db_name]):
                raise ValueError(
                    "Error, please set the POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_DBNAME environment variables or provide them in the config."
                )

            # Check if it's a Unix socket connection
            if host.startswith("/") and not port:
                DB_CONNECTION = (
                    f"postgresql://{user}:{password}@/{db_name}?host={host}"
                )
                logger.info("Using Unix socket connection")
            else:
                DB_CONNECTION = (
                    f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
                )
                logger.info("Using TCP connection")

        # The rest of the initialization remains the same
        try:
            self.vx: Client = create_client(DB_CONNECTION)
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to the pgvector provider with {DB_CONNECTION}."
            )

        self.collection_name = self.config.extra_fields.get(
            "vecs_collection"
        ) or os.getenv("POSTGRES_VECS_COLLECTION")
        if not self.collection_name:
            raise ValueError(
                "Error, please set a valid POSTGRES_VECS_COLLECTION environment variable or set a 'vecs_collection' in the 'database' settings of your `r2r.toml`."
            )

        self.collection: Optional[Collection] = None
        self._initialize_vector_db(dimension)
        logger.info(
            f"Successfully initialized PGVectorDB with collection: {self.collection_name}"
        )

    def _initialize_vector_db(self, dimension: int) -> None:
        self.collection = self.vx.get_or_create_collection(
            name=self.collection_name, dimension=dimension
        )

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
                    entry.group_ids,
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
                    entry.group_ids,
                    entry.vector.data,
                    entry.text,
                    entry.metadata,
                )
                for entry in entries
            ]
        )

    def get_document_groups(self, document_id: str) -> list[str]:
        query = text(
            f"""
            SELECT group_ids
            FROM document_info_{self.collection_name}
            WHERE document_id = :document_id
        """
        )
        with self.vx.Session() as sess:
            result = sess.execute(query, {"document_id": document_id})
            group_ids = result.scalar()
        return [str(group_id) for group_id in (group_ids or [])]

    def semantic_search(
        self, query_vector: list[float], search_settings: VectorSearchSettings
    ) -> list[VectorSearchResult]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `semantic_search`."
            )
        results = self.collection.query(
            vector=query_vector, search_settings=search_settings
        )
        return [
            VectorSearchResult(
                fragment_id=result[0],
                extraction_id=result[1],
                document_id=result[2],
                user_id=result[3],
                group_ids=result[4],
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
        from sqlalchemy import func, select
        from sqlalchemy.sql.expression import or_

        full_text_query = (
            select(
                self.collection.table.c.fragment_id,
                self.collection.table.c.extraction_id,
                self.collection.table.c.document_id,
                self.collection.table.c.user_id,
                self.collection.table.c.group_ids,
                self.collection.table.c.text,
                self.collection.table.c.metadata,
                func.ts_rank_cd(
                    func.to_tsvector("english", self.collection.table.c.text),
                    func.websearch_to_tsquery("english", query_text),
                    1 | 2 | 4 | 8 | 16 | 32 | 64,
                ).label("rank"),
                func.ts_headline(
                    "english",
                    self.collection.table.c.text,
                    func.websearch_to_tsquery("english", query_text),
                    "StartSel = <b>, StopSel = </b>, MaxWords=35, MinWords=15",
                ).label("headline"),
            )
            .where(
                or_(
                    func.to_tsvector(
                        "english", self.collection.table.c.text
                    ).op("@@")(
                        func.websearch_to_tsquery("english", query_text)
                    ),
                    func.similarity(self.collection.table.c.text, query_text)
                    > 0.3,
                )
            )
            .order_by(
                func.ts_rank_cd(
                    func.to_tsvector("english", self.collection.table.c.text),
                    func.websearch_to_tsquery("english", query_text),
                    1 | 2 | 4 | 8 | 16 | 32 | 64,
                ).desc()
            )
            .limit(search_settings.hybrid_search_settings.full_text_limit)
        )

        if search_settings.filters:
            full_text_query = full_text_query.where(
                self.collection.build_filters(search_settings.filters)
            )

        with self.vx.Session() as session:
            results = session.execute(full_text_query).fetchall()

        return [
            VectorSearchResult(
                fragment_id=result.fragment_id,
                extraction_id=result.extraction_id,
                document_id=result.document_id,
                user_id=result.user_id,
                group_ids=result.group_ids,
                text=result.text,
                score=float(result.rank),
                metadata={**result.metadata, "headline": result.headline},
            )
            for result in results
        ]

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
        semantic_results = self.semantic_search(query_vector, search_settings)
        full_text_results = self.full_text_search(
            query_text,
            search_settings,
        )

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
        combined_results = {}
        for rank, result in enumerate(semantic_results, 1):
            combined_results[result.fragment_id] = {
                "semantic_rank": rank,
                "full_text_rank": full_text_limit,
                "data": result,
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
                group_ids=result["data"].group_ids,
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

    def create_index(self, index_type, column_name, index_options):
        self.collection.create_index()

    def delete(
        self,
        filters: dict[str, Any],
    ) -> list[str]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `delete`."
            )

        return self.collection.delete(filters=filters)

    def get_document_chunks(self, document_id: str) -> list[dict]:
        if not self.collection:
            raise ValueError("Collection is not initialized.")

        table_name = self.collection.table.name
        query = text(
            f"""
            SELECT fragment_id, extraction_id, document_id, user_id, group_ids, text, metadata
            FROM vecs."{table_name}"
            WHERE document_id = :document_id
            ORDER BY CAST(metadata->>'chunk_order' AS INTEGER)
        """
        )

        params = {"document_id": document_id}

        with self.vx.Session() as sess:
            results = sess.execute(query, params).fetchall()
            return [
                {
                    "fragment_id": result[0],
                    "extraction_id": result[1],
                    "document_id": result[2],
                    "user_id": result[3],
                    "group_ids": result[4],
                    "text": result[5],
                    "metadata": result[6],
                }
                for result in results
            ]
