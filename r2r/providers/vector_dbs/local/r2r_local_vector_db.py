import json
import logging
import os
import sqlite3
import uuid
from typing import Optional, Union

from r2r.core import (
    DocumentInfo,
    UserStats,
    VectorDBConfig,
    VectorDBProvider,
    VectorEntry,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)


class R2RLocalVectorDB(VectorDBProvider):
    def __init__(self, config: VectorDBConfig) -> None:

        super().__init__(config)
        if config.provider != "local":
            raise ValueError(
                "R2RLocalVectorDB must be initialized with provider `local`."
            )

    def _get_conn(self):
        conn = sqlite3.connect(
            self.config.extra_fields.get("db_path")
            or os.getenv("LOCAL_DB_PATH", "local.sqlite")
        )
        return conn

    def _get_cursor(self, conn):
        return conn.cursor()

    def initialize_collection(self, dimension: int) -> None:
        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{self.config.collection_name}" (
                id TEXT PRIMARY KEY,
                vector TEXT,
                metadata TEXT
            )
        """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS document_info_{self.config.collection_name} (
                document_id TEXT PRIMARY KEY,
                title TEXT,
                user_id TEXT,
                version TEXT,
                size_in_bytes INT,
                created_at TEXT DEFAULT (DATETIME('now')),
                updated_at TEXT DEFAULT (DATETIME('now')),
                metadata TEXT
            );
        """
        )
        conn.commit()
        conn.close()

    def create_index(self, index_type, column_name, index_options):
        raise NotImplementedError(
            "R2RLocalVectorDB does not support creating indexes."
        )

    def copy(self, entry: VectorEntry, commit=True) -> None:
        if self.config.collection_name is None:
            raise ValueError(
                "Collection name is not set. Please call `initialize_collection` first."
            )

        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        serializeable_entry = entry.to_serializable()
        cursor.execute(
            f"""
                INSERT OR IGNORE INTO "{self.config.collection_name}" (id, vector, metadata)
                VALUES (?, ?, ?)
            """,
            (
                serializeable_entry["id"],
                str(serializeable_entry["vector"]),
                json.dumps(serializeable_entry["metadata"]),
            ),
        )
        if commit:
            conn.commit()
        conn.close()

    def upsert(self, entry: VectorEntry, commit=True) -> None:
        if self.config.collection_name is None:
            raise ValueError(
                "Collection name is not set. Please call `initialize_collection` first."
            )

        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        serializeable_entry = entry.to_serializable()
        cursor.execute(
            f"""
                INSERT OR REPLACE INTO "{self.config.collection_name}" (id, vector, metadata)
                VALUES (?, ?, ?)
            """,
            (
                serializeable_entry["id"],
                str(serializeable_entry["vector"]),
                json.dumps(serializeable_entry["metadata"]),
            ),
        )
        if commit:
            conn.commit()
        conn.close()

    def _cosine_similarity(
        self, vec1: list[float], vec2: list[float]
    ) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = sum(a * a for a in vec1) ** 0.5
        norm_b = sum(b * b for b in vec2) ** 0.5
        return dot_product / (norm_a * norm_b)

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Union[bool, int, str]] = {},
        limit: int = 10,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        if self.config.collection_name is None:
            raise ValueError(
                "Collection name is not set. Please call `initialize_collection` first."
            )
        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        cursor.execute(f'SELECT * FROM "{self.config.collection_name}"')
        results = []
        for id, vector, metadata in cursor.fetchall():
            vector = json.loads(vector)
            json_metadata = json.loads(metadata)
            if all(json_metadata.get(k) == v for k, v in filters.items()):
                # Local cosine similarity calculation
                score = self._cosine_similarity(query_vector, vector)
                results.append(
                    VectorSearchResult(
                        id=id, score=score, metadata=json_metadata
                    )
                )
        results.sort(key=lambda x: x.score, reverse=True)
        conn.close()
        return results[:limit]

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
        raise NotImplementedError(
            "Hybrid search is not supported in R2RLocalVectorDB."
        )

    def delete_by_metadata(
        self,
        metadata_fields: list[str],
        metadata_values: list[Union[bool, int, str]],
    ) -> list[str]:
        super().delete_by_metadata(metadata_fields, metadata_values)
        if self.config.collection_name is None:
            raise ValueError(
                "Collection name is not set. Please call `initialize_collection` first."
            )

        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        cursor.execute(f'SELECT * FROM "{self.config.collection_name}"')
        deleted_ids = set([])
        for id, _, metadata in cursor.fetchall():
            metadata_json = json.loads(metadata)
            is_valid = True
            for metadata_field, metadata_value in zip(
                metadata_fields, metadata_values
            ):
                if metadata_json.get(metadata_field) != metadata_value:
                    is_valid = False
                    break
            if is_valid:
                cursor.execute(
                    f'DELETE FROM "{self.config.collection_name}" WHERE id = ?',
                    (id,),
                )
                deleted_ids.add(metadata_json.get("document_id", None))
        conn.commit()
        conn.close()
        return list(deleted_ids)

    def get_metadatas(
        self,
        metadata_fields: list[str],
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> list[str]:
        if self.config.collection_name is None:
            raise ValueError(
                "Collection name is not set. Please call `initialize_collection` first."
            )
        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        cursor.execute(f'SELECT metadata FROM "{self.config.collection_name}"')
        results = set([])
        for (metadata,) in cursor.fetchall():
            metatada_json = json.loads(metadata)
            if (
                filter_field is None
                or metatada_json.get(filter_field) == filter_value
            ):
                results.add(
                    json.dumps(
                        {
                            k: metatada_json.get(k, None)
                            for k in metadata_fields
                        }
                    )
                )
        conn.close()
        return [json.loads(r) for r in results]

    def upsert_documents_overview(
        self, documents_overview: list[DocumentInfo]
    ) -> None:
        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        for document_info in documents_overview:
            db_entry = document_info.convert_to_db_entry()
            cursor.execute(
                f"""
                INSERT INTO document_info_{self.config.collection_name} (document_id, title, user_id, version, size_in_bytes, metadata, created_at, updated_at)
                VALUES (:document_id, :title, :user_id, :version, :size_in_bytes, :metadata, :created_at, :updated_at)
                ON CONFLICT(document_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    user_id = EXCLUDED.user_id,
                    version = EXCLUDED.version,
                    updated_at = EXCLUDED.updated_at,
                    size_in_bytes = EXCLUDED.size_in_bytes,
                    metadata = EXCLUDED.metadata;
                """,
                db_entry,
            )
        conn.commit()
        conn.close()

    def delete_documents_overview(self, document_ids: list[str]) -> None:
        conn = self._get_conn()
        cursor = self._get_cursor(conn)

        # Create a placeholder string for the SQL query
        placeholders = ", ".join("?" for _ in document_ids)

        # Execute the deletion query with the list of document IDs
        cursor.execute(
            f"""
            DELETE FROM document_info_{self.config.collection_name} WHERE document_id IN ({placeholders});
            """,
            document_ids,
        )

        conn.commit()
        conn.close()

    def get_documents_overview(
        self,
        filter_document_ids: Optional[list[str]] = None,
        filter_user_ids: Optional[list[str]] = None,
    ) -> list[DocumentInfo]:
        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        query = f"""
        SELECT document_id, title, user_id, version, size_in_bytes, created_at, updated_at, metadata
        FROM document_info_{self.config.collection_name}
        """

        conditions = []
        params = []

        if filter_document_ids:
            placeholders = ", ".join("?" for _ in filter_document_ids)
            conditions.append(f"document_id IN ({placeholders})")
            params.extend(filter_document_ids)
        if filter_user_ids:
            placeholders = ", ".join("?" for _ in filter_user_ids)
            conditions.append(f"user_id IN ({placeholders})")
            params.extend(filter_user_ids)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        document_infos = []
        for row in results:
            document_info = DocumentInfo(
                document_id=uuid.UUID(row[0]),
                title=row[1],
                user_id=(
                    uuid.UUID(row[2])
                    if (row[2] != "None" and row[2] is not None)
                    else None
                ),
                version=row[3],
                size_in_bytes=row[4],
                created_at=row[5],
                updated_at=row[6],
                metadata=json.loads(row[7]),
            )
            document_infos.append(document_info)

        return document_infos

    def get_document_chunks(self, document_id: str) -> list[str]:
        if not self.config.collection_name:
            raise ValueError(
                "Collection name is not set. Please call `initialize_collection` first."
            )

        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        query = f"""
            SELECT metadata
            FROM "{self.config.collection_name}"
            WHERE json_extract(metadata, '$.document_id') = ?
            ORDER BY CAST(json_extract(metadata, '$.chunk_order') AS INTEGER)
        """
        cursor.execute(query, (document_id,))
        results = cursor.fetchall()
        conn.close()
        return [json.loads(result[0]) for result in results]

    def get_users_overview(self, user_ids: Optional[list[str]] = None):
        user_ids_condition = ""
        params = []
        if user_ids:
            user_ids_condition = (
                "WHERE user_id IN (" + ",".join("?" for _ in user_ids) + ")"
            )
            params = user_ids

        query = f"""
            SELECT user_id, COUNT(document_id) AS num_files, SUM(size_in_bytes) AS total_size_in_bytes, GROUP_CONCAT(document_id) AS document_ids
            FROM document_info_{self.config.collection_name}
            {user_ids_condition}
            GROUP BY user_id
        """

        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return [
            UserStats(
                user_id=uuid.UUID(row[0]),
                num_files=row[1],
                total_size_in_bytes=row[2],
                document_ids=[
                    uuid.UUID(doc_id) for doc_id in row[3].split(",")
                ],
            )
            for row in results
        ]
