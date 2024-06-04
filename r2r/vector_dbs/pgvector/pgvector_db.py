import json
from datetime import datetime
from sqlalchemy import text
import logging
import os
from typing import Optional, Union

from r2r.core import (
    SearchResult,
    VectorDBConfig,
    VectorDBProvider,
    VectorEntry,
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
                f"Error, PGVectorDB requires the vecs library. Please run `poetry add vecs`."
            )
        user = os.getenv("POSTGRES_USER")
        password = os.getenv("POSTGRES_PASSWORD")
        host = os.getenv("POSTGRES_HOST")
        port = os.getenv("POSTGRES_PORT")
        db_name = os.getenv("POSTGRES_DBNAME")
        if not all([user, password, host, port, db_name]):
            raise ValueError(
                "Error, please set the POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, and POSTGRES_DBNAME environment variables."
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
        self.collection: Optional[Collection] = None
        self.config: VectorDBConfig = config

    def initialize_collection(self, dimension: int) -> None:
        self.collection = self.vx.get_or_create_collection(
            name=self.config.collection_name, dimension=dimension
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
    ) -> list[SearchResult]:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `search`."
            )
        measure = kwargs.get("measure", "cosine_distance")
        mapped_filters = {
            key: {"$eq": value} for key, value in filters.items()
        }

        return [
            SearchResult(id=ele[0], score=float(1 - ele[1]), metadata=ele[2])  # type: ignore
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


    def delete_by_metadata(
        self, metadata_fields: str, metadata_values: Union[bool, int, str]
    ) -> None:
        super().delete_by_metadata(metadata_fields, metadata_values)
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `delete_by_metadata`."
            )
        self.collection.delete(
            filters={k: {"$eq": v} for k, v in zip(metadata_fields, metadata_values)}
        )
        self.delete_document_info_by_metadata(metadata_fields, metadata_values)

    def delete_document_info_by_metadata(
        self, metadata_fields: str, metadata_values: Union[bool, int, str]
    ) -> None:
        filters = {k: v for k, v in zip(metadata_fields, metadata_values)}
        query = text(f"""
        DELETE FROM document_info WHERE {" AND ".join([f"{k} = :{k}" for k in filters.keys()])};
        """)
        with self.vx.Session() as sess:
            with sess.begin():
                sess.execute(query, filters)

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
    
    def upsert_document_info(self, document_info: dict) -> None:
        # Extract and remove the fields from the metadata
        metadata = document_info.pop("metadata", None)
        if metadata is None:
            metadata = {}
        else:
            metadata = json.loads(metadata)
        document_info["user_id"] = metadata.pop("user_id", "")
        document_info["title"] = metadata.pop("title", "")
        document_info["created_at"] = datetime.now()  # Use the latest timestamp
        document_info["updated_at"] = datetime.now()  # Use the latest timestamp

        # Convert remaining metadata to JSON
        document_info["metadata"] = json.dumps(metadata)

        query = text("""
        INSERT INTO document_info (document_id, title, user_id, version, created_at, updated_at, size_in_bytes, metadata)
        VALUES (:document_id, :title, :user_id, :version, :created_at, :updated_at, :size_in_bytes, :metadata)
        ON CONFLICT (document_id) DO UPDATE SET
        title = EXCLUDED.title,
        user_id = EXCLUDED.user_id,
        version = EXCLUDED.version,
        updated_at = EXCLUDED.updated_at,
        size_in_bytes = EXCLUDED.size_in_bytes,
        metadata = EXCLUDED.metadata;
        """)
        with self.vx.Session() as sess:
            with sess.begin():
                sess.execute(query, document_info)

    def delete_document_info(self, document_id: str) -> None:
        query = text("""
        DELETE FROM document_info WHERE document_id = :document_id;
        """)
        with self.vx.Session() as sess:
            with sess.begin():
                sess.execute(query, {"document_id": document_id})