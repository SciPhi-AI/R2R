import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Union

from r2r.core import (
    SearchResult,
    VectorDBConfig,
    VectorDBProvider,
    VectorEntry,
)

logger = logging.getLogger(__name__)


@dataclass
class LocalVectorDBConfig(VectorDBConfig):
    db_path: Optional[str] = None

    @property
    def supported_providers(self) -> List[str]:
        return ["local"]


class LocalVectorDBProvider(VectorDBProvider):
    def __init__(self, config: LocalVectorDBConfig) -> None:
        logger.info(
            "Initializing `LocalVectorDBProvider` to store and retrieve embeddings."
        )

        super().__init__(config)
        if config.provider != "local":
            raise ValueError(
                "LocalVectorDBProvider must be initialized with provider `local`."
            )

    def _get_conn(self):
        conn = sqlite3.connect(
            self.config.db_path or os.getenv("LOCAL_DB_PATH", "local.sqlite")
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
        conn.commit()
        conn.close()

    def create_index(self, index_type, column_name, index_options):
        raise NotImplementedError(
            "LocalVectorDBProvider does not support creating indexes."
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
    ) -> list[SearchResult]:
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
            if all(metadata.get(k) == v for k, v in filters.items()):
                # Local cosine similarity calculation
                score = self._cosine_similarity(query_vector, vector)
                results.append(SearchResult(id=id, score=score, metadata=json_metadata))
        results.sort(key=lambda x: x.score, reverse=True)
        conn.close()
        return results[:limit]

    def delete_by_metadata(
        self, key: str, value: Union[bool, int, str]
    ) -> None:
        if self.config.collection_name is None:
            raise ValueError(
                "Collection name is not set. Please call `initialize_collection` first."
            )

        conn = self._get_conn()
        cursor = self._get_cursor(conn)
        cursor.execute(f'SELECT * FROM "{self.config.collection_name}"')
        for id, vector, metadata in cursor.fetchall():
            metadata = json.loads(metadata)
            if metadata.get(key) == value:
                cursor.execute(
                    f'DELETE FROM "{self.config.collection_name}" WHERE id = ?',
                    (id,),
                )
        conn.commit()
        conn.close()

    def get_all_unique_values(
        self,
        metadata_field: str,
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
        unique_values = set()
        for (metadata,) in cursor.fetchall():
            metadata = json.loads(metadata)
            if (
                filter_field is None
                or metadata.get(filter_field) == filter_value
            ):
                if metadata_field in metadata:
                    unique_values.add(metadata[metadata_field])
        conn.close()
        return list(unique_values)

    def close(self):
        pass

    def close(self):
        pass
