import json
import logging
import os
import time
from typing import Literal, Optional, Union

from sqlalchemy import exc, text

from r2r.base import (
    DocumentInfo,
    UserStats,
    VectorDBConfig,
    VectorDBProvider,
    VectorEntry,
    VectorSearchResult,
)
from r2r.vecs.client import Client
from r2r.vecs.collection import Collection

logger = logging.getLogger(__name__)


class PGVectorDB(VectorDBProvider):
    def __init__(self, config: VectorDBConfig) -> None:
        super().__init__(config)
        try:
            import r2r.vecs
        except ImportError:
            raise ValueError(
                f"Error, PGVectorDB requires the vecs library. Please run `pip install vecs`."
            )
        user = self.config.extra_fields.get("user", None) or os.getenv(
            "POSTGRES_USER"
        )
        if not user:
            raise ValueError(
                "Error, please set a valid POSTGRES_USER environment variable or set a 'user' in the 'vector_database' settings of your `config.json`."
            )
        password = self.config.extra_fields.get("password", None) or os.getenv(
            "POSTGRES_PASSWORD"
        )
        if not password:
            raise ValueError(
                "Error, please set a valid POSTGRES_PASSWORD environment variable or set a 'password' in the 'vector_database' settings of your `config.json`."
            )

        host = self.config.extra_fields.get("host", None) or os.getenv(
            "POSTGRES_HOST"
        )
        if not host:
            raise ValueError(
                "Error, please set a valid POSTGRES_HOST environment variable or set a 'host' in the 'vector_database' settings of your `config.json`."
            )

        port = self.config.extra_fields.get("port", None) or os.getenv(
            "POSTGRES_PORT"
        )
        if not port:
            raise ValueError(
                "Error, please set a valid POSTGRES_PORT environment variable or set a 'port' in the 'vector_database' settings of your `config.json`."
            )

        db_name = self.config.extra_fields.get("db_name", None) or os.getenv(
            "POSTGRES_DBNAME"
        )
        if not db_name:
            raise ValueError(
                "Error, please set a valid POSTGRES_DBNAME environment variable or set a 'db_name' in the 'vector_database' settings of your `config.json`."
            )

        collection = self.config.extra_fields.get(
            "vecs_collection", None
        ) or os.getenv("POSTGRES_VECS_COLLECTION")
        if not collection:
            raise ValueError(
                "Error, please set a valid POSTGRES_VECS_COLLECTION environment variable or set a 'collection' in the 'vector_database' settings of your `config.json`."
            )

        if not all([user, password, host, port, db_name, collection]):
            raise ValueError(
                "Error, please set the POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DBNAME, and POSTGRES_VECS_COLLECTION environment variables to use pgvector database."
            )
        try:
            DB_CONNECTION = (
                f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
            )
            self.vx: Client = r2r.vecs.create_client(DB_CONNECTION)
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to the pgvector provider with {DB_CONNECTION}."
            )
        self.collection_name = collection
        self.collection: Optional[Collection] = None
        self.config: VectorDBConfig = config

    def initialize_collection(self, dimension: int) -> None:
        self.collection = self.vx.get_or_create_collection(
            name=self.collection_name, dimension=dimension
        )
        self._create_document_info_table()
        self._create_hybrid_search_function()

    def _create_document_info_table(self):
        with self.vx.Session() as sess:
            with sess.begin():
                try:
                    # Enable uuid-ossp extension
                    sess.execute(
                        text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
                    )
                except exc.ProgrammingError as e:
                    logger.error(f"Error enabling uuid-ossp extension: {e}")
                    raise

                query = f"""
                CREATE TABLE IF NOT EXISTS document_info_{self.collection_name} (
                    document_id UUID PRIMARY KEY,
                    title TEXT,
                    user_id UUID NULL,
                    version TEXT,
                    size_in_bytes INT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    metadata JSONB
                );
                """
                sess.execute(text(query))
                sess.commit()

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
        RETURNS SETOF vecs."{self.collection_name}"
        LANGUAGE sql
        AS $$
        WITH full_text AS (
            SELECT
                id,
                ROW_NUMBER() OVER (ORDER BY ts_rank(to_tsvector('english', metadata->>'text'), websearch_to_tsquery(query_text)) DESC) AS rank_ix
            FROM vecs."{self.collection_name}"
            WHERE to_tsvector('english', metadata->>'text') @@ websearch_to_tsquery(query_text)
            AND (filter_condition IS NULL OR (metadata @> filter_condition))
            ORDER BY rank_ix
            LIMIT LEAST(match_limit, 30) * 2
        ),
        semantic AS (
            SELECT
                id,
                ROW_NUMBER() OVER (ORDER BY vec <#> query_embedding) AS rank_ix
            FROM vecs."{self.collection_name}"
            WHERE filter_condition IS NULL OR (metadata @> filter_condition)
            ORDER BY rank_ix
            LIMIT LEAST(match_limit, 30) * 2
        )
        SELECT
            vecs."{self.collection_name}".*
        FROM
            full_text
            FULL OUTER JOIN semantic
                ON full_text.id = semantic.id
            JOIN vecs."{self.collection_name}"
                ON vecs."{self.collection_name}".id = COALESCE(full_text.id, semantic.id)
        ORDER BY
            COALESCE(1.0 / (rrf_k + full_text.rank_ix), 0.0) * full_text_weight +
            COALESCE(1.0 / (rrf_k + semantic.rank_ix), 0.0) * semantic_weight
            DESC
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

    def copy(self, entry: VectorEntry, commit=True) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `copy`."
            )

        serializeable_entry = entry.to_serializable()

        self.collection.copy(
            records=[
                (
                    serializeable_entry["id"],
                    serializeable_entry["vector"],
                    serializeable_entry["metadata"],
                )
            ]
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
                (
                    str(entry.id),
                    entry.vector.data,
                    entry.to_serializable()["metadata"],
                )
                for entry in entries
            ]
        )

    def upsert(self, entry: VectorEntry, commit=True) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )

        self.collection.upsert(
            records=[
                (
                    str(entry.id),
                    entry.vector.data,
                    entry.to_serializable()["metadata"],
                )
            ]
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
                (
                    str(entry.id),
                    entry.vector.data,
                    entry.to_serializable()["metadata"],
                )
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
            VectorSearchResult(id=ele[0], score=float(1 - ele[1]), metadata=ele[2])  # type: ignore
            for ele in self.collection.query(
                data=query_vector,
                limit=limit,
                filters=mapped_filters,
                measure=measure,
                include_value=True,
                include_metadata=True,
            )
        ]

    def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        limit: int = 10,
        filters: Optional[dict[str, Union[bool, int, str]]] = None,
        # Hybrid search parameters
        full_text_weight: float = 1.0,
        semantic_weight: float = 1.0,
        rrf_k: int = 20,  # typical value is ~2x the number of results you want
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `hybrid_search`."
            )

        # Convert filters to a JSON-compatible format
        filter_condition = None
        if filters:
            filter_condition = json.dumps(filters)

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
            result = session.execute(query, params).fetchall()
        return [
            VectorSearchResult(id=row[0], score=1.0, metadata=row[-1])
            for row in result
        ]

    def create_index(self, index_type, column_name, index_options):
        pass

    def delete_by_metadata(
        self,
        metadata_fields: list[str],
        metadata_values: list[Union[bool, int, str]],
        logic: Literal["AND", "OR"] = "AND",
    ) -> list[str]:
        if logic == "OR":
            raise ValueError(
                "OR logic is still being tested before official support for `delete_by_metadata` in pgvector."
            )
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `delete_by_metadata`."
            )

        if len(metadata_fields) != len(metadata_values):
            raise ValueError(
                "The number of metadata fields must match the number of metadata values."
            )

        # Construct the filter
        if logic == "AND":
            filters = {
                k: {"$eq": v} for k, v in zip(metadata_fields, metadata_values)
            }
        else:  # OR logic
            # TODO - Test 'or' logic and remove check above
            filters = {
                "$or": [
                    {k: {"$eq": v}}
                    for k, v in zip(metadata_fields, metadata_values)
                ]
            }

        print(f"Deleting with filters: {filters}")
        return self.collection.delete(filters=filters)

    def get_metadatas(
        self,
        metadata_fields: list[str],
        filter_field: Optional[str] = None,
        filter_value: Optional[Union[bool, int, str]] = None,
    ) -> list[dict]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `get_metadatas`."
            )

        results = {tuple(metadata_fields): {}}
        for field in metadata_fields:
            unique_values = self.collection.get_unique_metadata_values(
                field=field,
                filter_field=filter_field,
                filter_value=filter_value,
            )
            for value in unique_values:
                if value not in results:
                    results[value] = {}
                results[value][field] = value

        return [
            results[key] for key in results if key != tuple(metadata_fields)
        ]

    def upsert_documents_overview(
        self, documents_overview: list[DocumentInfo]
    ) -> None:
        for document_info in documents_overview:
            db_entry = document_info.convert_to_db_entry()

            # Convert 'None' string to None type for user_id
            if db_entry["user_id"] == "None":
                db_entry["user_id"] = None

            query = text(
                f"""
                INSERT INTO document_info_{self.collection_name} (document_id, title, user_id, version, created_at, updated_at, size_in_bytes, metadata)
                VALUES (:document_id, :title, :user_id, :version, :created_at, :updated_at, :size_in_bytes, :metadata)
                ON CONFLICT (document_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    user_id = EXCLUDED.user_id,
                    version = EXCLUDED.version,
                    updated_at = EXCLUDED.updated_at,
                    size_in_bytes = EXCLUDED.size_in_bytes,
                    metadata = EXCLUDED.metadata;
            """
            )
            with self.vx.Session() as sess:
                sess.execute(query, db_entry)
                sess.commit()

    def delete_documents_overview(self, document_ids: list[str]) -> None:
        placeholders = ", ".join(
            f":doc_id_{i}" for i in range(len(document_ids))
        )
        query = text(
            f"""
            DELETE FROM document_info_{self.collection_name} WHERE document_id IN ({placeholders});
            """
        )
        params = {
            f"doc_id_{i}": document_id
            for i, document_id in enumerate(document_ids)
        }

        with self.vx.Session() as sess:
            with sess.begin():
                sess.execute(query, params)
            sess.commit()

    def get_documents_overview(
        self,
        filter_document_ids: Optional[list[str]] = None,
        filter_user_ids: Optional[list[str]] = None,
    ):
        conditions = []
        params = {}

        if filter_document_ids:
            placeholders = ", ".join(
                f":doc_id_{i}" for i in range(len(filter_document_ids))
            )
            conditions.append(f"document_id IN ({placeholders})")
            params.update(
                {
                    f"doc_id_{i}": str(document_id)
                    for i, document_id in enumerate(filter_document_ids)
                }
            )
        if filter_user_ids:
            placeholders = ", ".join(
                f":user_id_{i}" for i in range(len(filter_user_ids))
            )
            conditions.append(f"user_id IN ({placeholders})")
            params.update(
                {
                    f"user_id_{i}": str(user_id)
                    for i, user_id in enumerate(filter_user_ids)
                }
            )

        query = f"""
            SELECT document_id, title, user_id, version, size_in_bytes, created_at, updated_at, metadata
            FROM document_info_{self.collection_name}
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        with self.vx.Session() as sess:
            results = sess.execute(text(query), params).fetchall()
            return [
                DocumentInfo(
                    document_id=row[0],
                    title=row[1],
                    user_id=row[2],
                    version=row[3],
                    size_in_bytes=row[4],
                    created_at=row[5],
                    updated_at=row[6],
                    metadata=row[7],
                )
                for row in results
            ]

    def get_document_chunks(self, document_id: str) -> list[dict]:
        if not self.collection:
            raise ValueError("Collection is not initialized.")

        table_name = self.collection.table.name
        query = text(
            f"""
            SELECT metadata
            FROM vecs."{table_name}"
            WHERE metadata->>'document_id' = :document_id
            ORDER BY CAST(metadata->>'chunk_order' AS INTEGER)
        """
        )

        params = {"document_id": document_id}

        with self.vx.Session() as sess:
            results = sess.execute(query, params).fetchall()
            return [result[0] for result in results]

    def get_users_overview(self, user_ids: Optional[list[str]] = None):
        user_ids_condition = ""
        params = {}
        if user_ids:
            user_ids_condition = "WHERE user_id IN :user_ids"
            params["user_ids"] = tuple(
                map(str, user_ids)
            )  # Convert UUIDs to strings

        query = f"""
            SELECT user_id, COUNT(document_id) AS num_files, SUM(size_in_bytes) AS total_size_in_bytes, ARRAY_AGG(document_id) AS document_ids
            FROM document_info_{self.collection_name}
            {user_ids_condition}
            GROUP BY user_id
        """

        with self.vx.Session() as sess:
            results = sess.execute(text(query), params).fetchall()
        return [
            UserStats(
                user_id=row[0],
                num_files=row[1],
                total_size_in_bytes=row[2],
                document_ids=row[3],
            )
            for row in results
            if row[0] is not None
        ]
