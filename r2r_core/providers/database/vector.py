import json
import logging
import os
import time
from typing import Any, Optional

from sqlalchemy import exc, text
from sqlalchemy.engine.url import make_url

from r2r_core.base import (
    DatabaseConfig,
    VectorDBProvider,
    VectorEntry,
    VectorSearchResult,
    generate_id_from_label,
)

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
        self._create_hybrid_search_function()
        logger.info(
            f"Successfully initialized PGVectorDB with collection: {self.collection_name}"
        )

    def _initialize_vector_db(self, dimension: int) -> None:
        self.collection = self.vx.get_or_create_collection(
            name=self.collection_name, dimension=dimension
        )

    def _create_hybrid_search_function(self):
        hybrid_search_function = f"""
        CREATE OR REPLACE FUNCTION hybrid_search_{self.collection_name}(
            query_text TEXT,
            query_embedding VECTOR(512),
            match_limit INT,
            full_text_weight FLOAT = 1,
            semantic_weight FLOAT = 1,
            rrf_k INT = 50,
            filter_condition JSONB = NULL
        )
        RETURNS TABLE(
            fragment_id UUID,
            extraction_id UUID,
            document_id UUID,
            user_id UUID,
            group_ids UUID[],
            vec VECTOR(512),
            text TEXT,
            metadata JSONB,
            rrf_score FLOAT,
            semantic_score FLOAT,
            full_text_score FLOAT,
            rank_semantic INT,
            rank_full_text INT
        )
        LANGUAGE sql
        AS $$
        WITH full_text AS (
            SELECT
                fragment_id,
                ts_rank_cd(to_tsvector('english', text), websearch_to_tsquery('english', query_text), 1 | 2 | 4 | 8 | 16 | 32 | 64) * 10000 AS full_text_score,
                ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('english', text), websearch_to_tsquery('english', query_text), 1 | 2 | 4 | 8 | 16 | 32 | 64) DESC) AS rank_ix
            FROM vecs."{self.collection_name}"
            WHERE to_tsvector('english', text) @@ websearch_to_tsquery('english', query_text)
            AND (filter_condition IS NULL OR (metadata @> filter_condition))
            ORDER BY rank_ix
            LIMIT LEAST(match_limit, 30) * 2
        ),
        semantic AS (
            SELECT
                fragment_id,
                1 - (vec <=> query_embedding) AS semantic_score,
                ROW_NUMBER() OVER (ORDER BY (vec <=> query_embedding)) AS rank_ix
            FROM vecs."{self.collection_name}"
            WHERE filter_condition IS NULL OR (metadata @> filter_condition)
            ORDER BY rank_ix
            LIMIT LEAST(match_limit, 30) * 2
        )
        SELECT
            vecs."{self.collection_name}".fragment_id,
            vecs."{self.collection_name}".extraction_id,
            vecs."{self.collection_name}".document_id,
            vecs."{self.collection_name}".user_id,
            vecs."{self.collection_name}".group_ids,
            vecs."{self.collection_name}".vec,
            vecs."{self.collection_name}".text,
            vecs."{self.collection_name}".metadata,
            (COALESCE(1.0 / (rrf_k + full_text.rank_ix), 0.0) * full_text_weight +
            COALESCE(1.0 / (rrf_k + semantic.rank_ix), 0.0) * semantic_weight) AS rrf_score,
            COALESCE(semantic.semantic_score, 0) AS semantic_score,
            COALESCE(full_text.full_text_score, 0) AS full_text_score,
            semantic.rank_ix AS rank_semantic,
            full_text.rank_ix AS rank_full_text
        FROM
            full_text
            FULL OUTER JOIN semantic
                ON full_text.fragment_id = semantic.fragment_id
            JOIN vecs."{self.collection_name}"
                ON vecs."{self.collection_name}".fragment_id = COALESCE(full_text.fragment_id, semantic.fragment_id)
        ORDER BY
            rrf_score DESC
        LIMIT
            LEAST(match_limit, 30);
        $$;
        """
        retry_attempts = 5
        for attempt in range(retry_attempts):
            try:
                with self.vx.Session() as sess:
                    # Acquire an advisory lock
                    sess.execute(text("SELECT pg_advisory_lock(123456789)"))
                    try:
                        sess.execute(text(hybrid_search_function))
                        sess.commit()
                    finally:
                        # Release the advisory lock
                        sess.execute(
                            text("SELECT pg_advisory_unlock(123456789)")
                        )
                break  # Break the loop if successful
            except exc.InternalError as e:
                if "tuple concurrently updated" in str(e):
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    raise  # Re-raise the exception if it's not a concurrency issue
        else:
            raise RuntimeError(
                "Failed to create hybrid search function after multiple attempts"
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

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Any] = {},
        limit: int = 10,
        measure: str = "cosine_distance",
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `search`."
            )
        results = self.collection.query(
            vector=query_vector,
            filters=filters,
            limit=limit,
            imeasure=measure,
            include_value=True,
            include_metadata=True,
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

    def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] = {},
        full_text_weight: float = 1.0,
        semantic_weight: float = 1.0,
        rrf_k: int = 20,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `hybrid_search`."
            )

        # Convert filters to a JSON-compatible format
        filter_condition = json.dumps(filters) if filters else None

        query = text(
            f"""
            SELECT * FROM hybrid_search_{self.collection_name}(
                cast(:query_text as TEXT), cast(:query_embedding as VECTOR), cast(:match_limit as INT),
                cast(:full_text_weight as FLOAT), cast(:semantic_weight as FLOAT), cast(:rrf_k as INT),
                cast(:filter_condition as JSONB)
            )
        """
        )

        params = {
            "query_text": str(query_text),
            "query_embedding": list(query_vector),
            "match_limit": limit,
            "full_text_weight": full_text_weight,
            "semantic_weight": semantic_weight,
            "rrf_k": rrf_k,
            "filter_condition": filter_condition,
        }

        with self.vx.Session() as session:
            results = session.execute(query, params).fetchall()
        return [
            VectorSearchResult(
                fragment_id=result[0],
                extraction_id=result[1],
                document_id=result[2],
                user_id=result[3],
                group_ids=result[4],
                text=result[6],
                metadata={
                    **result[7],
                    "semantic_score": result[9],
                    "semantic_rank": result[11],
                    "full_text_score": result[10],
                    "full_text_rank": result[12],
                },
                score=result[8],
            )
            for result in results
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
