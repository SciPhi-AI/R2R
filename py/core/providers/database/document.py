from typing import Optional
from uuid import UUID

from core.base import DocumentInfo, DocumentStatus, DocumentType, R2RException
from core.base.api.models.management.responses import GroupResponse

from .base import DatabaseMixin


class DocumentMixin(DatabaseMixin):

    def create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('document_info')} (
            document_id UUID PRIMARY KEY,
            group_ids UUID[],
            user_id UUID,
            type TEXT,
            metadata JSONB,
            title TEXT,
            version TEXT,
            size_in_bytes INT,
            ingestion_status TEXT DEFAULT 'processing',
            restructuring_status TEXT DEFAULT 'processing',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_group_ids_{self.collection_name}
        ON {self._get_table_name('document_info')} USING GIN (group_ids);
        """
        self.execute_query(query)

    def upsert_documents_overview(
        self, documents_overview: list[DocumentInfo]
    ) -> None:
        for document_info in documents_overview:
            query = f"""
            INSERT INTO {self._get_table_name('document_info')}
            (document_id, group_ids, user_id, type, metadata, title, version, size_in_bytes, ingestion_status, restructuring_status, created_at, updated_at)
            VALUES (:document_id, :group_ids, :user_id, :type, :metadata, :title, :version, :size_in_bytes, :ingestion_status, :restructuring_status, :created_at, :updated_at)
            ON CONFLICT (document_id) DO UPDATE SET
                group_ids = EXCLUDED.group_ids,
                user_id = EXCLUDED.user_id,
                type = EXCLUDED.type,
                metadata = EXCLUDED.metadata,
                title = EXCLUDED.title,
                version = EXCLUDED.version,
                size_in_bytes = EXCLUDED.size_in_bytes,
                ingestion_status = EXCLUDED.ingestion_status,
                restructuring_status = EXCLUDED.restructuring_status,
                updated_at = EXCLUDED.updated_at;
            """
            self.execute_query(query, document_info.convert_to_db_entry())

    def delete_from_documents_overview(
        self, document_id: str, version: Optional[str] = None
    ) -> None:
        query = f"""
            DELETE FROM {self._get_table_name('document_info')}
            WHERE document_id = :document_id
        """
        params = {"document_id": document_id}

        if version is not None:
            query += " AND version = :version"
            params["version"] = version

        self.execute_query(query, params)

    def get_documents_overview(
        self,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_group_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = 100,
    ):
        conditions = []
        params = {"offset": offset}
        if limit != -1:
            params["limit"] = limit

        if filter_document_ids:
            conditions.append("document_id = ANY(:document_ids)")
            params["document_ids"] = filter_document_ids

        if filter_user_ids:
            conditions.append("user_id = ANY(:user_ids)")
            params["user_ids"] = filter_user_ids

        if filter_group_ids:
            conditions.append("group_ids && :group_ids")
            params["group_ids"] = filter_group_ids

        query = f"""
            SELECT document_id, group_ids, user_id, type, metadata, title, version, size_in_bytes, ingestion_status, created_at, updated_at, restructuring_status
            FROM {self._get_table_name('document_info')}
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        limit_clause = "" if limit == -1 else f"LIMIT {limit}"
        query += f"""
            ORDER BY created_at DESC
            OFFSET :offset
            {limit_clause}
        """

        results = self.execute_query(query, params).fetchall()
        documents = [
            DocumentInfo(
                id=row[0],
                group_ids=row[1],
                user_id=row[2],
                type=DocumentType(row[3]),
                metadata=row[4],
                title=row[5],
                version=row[6],
                size_in_bytes=row[7],
                ingestion_status=DocumentStatus(row[8]),
                created_at=row[9],
                updated_at=row[10],
                restructuring_status=row[11],
            )
            for row in results
        ]

        # Get total count for pagination metadata
        count_query = f"""
            SELECT COUNT(*)
            FROM {self._get_table_name('document_info')}
        """
        if conditions:
            count_query += " WHERE " + " AND ".join(conditions)

        return documents
