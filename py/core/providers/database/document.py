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
            status TEXT DEFAULT 'processing',
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
            (document_id, group_ids, user_id, type, metadata, title, version, size_in_bytes, status, created_at, updated_at)
            VALUES (:document_id, :group_ids, :user_id, :type, :metadata, :title, :version, :size_in_bytes, :status, :created_at, :updated_at)
            ON CONFLICT (document_id) DO UPDATE SET
                group_ids = EXCLUDED.group_ids,
                user_id = EXCLUDED.user_id,
                type = EXCLUDED.type,
                metadata = EXCLUDED.metadata,
                title = EXCLUDED.title,
                version = EXCLUDED.version,
                size_in_bytes = EXCLUDED.size_in_bytes,
                status = EXCLUDED.status,
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
    ):
        conditions = []
        params = {}

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
            SELECT document_id, group_ids, user_id, type, metadata, title, version, size_in_bytes, status, created_at, updated_at
            FROM {self._get_table_name('document_info')}
        """
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        results = self.execute_query(query, params).fetchall()
        return [
            DocumentInfo(
                id=row[0],
                group_ids=row[1],
                user_id=row[2],
                type=DocumentType(row[3]),
                metadata=row[4],
                title=row[5],
                version=row[6],
                size_in_bytes=row[7],
                status=DocumentStatus(row[8]),
                created_at=row[9],
                updated_at=row[10],
            )
            for row in results
        ]
    
    def document_groups(self, document_id: UUID) -> list[GroupResponse]:
        query = f"""
            SELECT g.group_id, g.name, g.description, g.created_at, g.updated_at
            FROM {self._get_table_name('groups')} g
            JOIN {self._get_table_name('document_info')} d ON g.group_id = ANY(d.group_ids)
            WHERE d.document_id = :document_id
        """
        params = {"document_id": document_id}
        results = self.execute_query(query, params).fetchall()

        return [
            GroupResponse(
                group_id=row[0],
                name=row[1],
                description=row[2],
                created_at=row[3],
                updated_at=row[4],
            )
            for row in results
        ]
        
    def remove_document_from_group(self, document_id: UUID, group_id: UUID) -> None:
        """
        Remove a document from a group.

        Args:
            document_id (UUID): The ID of the document to remove.
            group_id (UUID): The ID of the group to remove the document from.

        Raises:
            R2RException: If the group doesn't exist or if the document is not in the group.
        """
        if not self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('document_info')}
            SET group_ids = array_remove(group_ids, :group_id)
            WHERE document_id = :document_id AND :group_id = ANY(group_ids)
            RETURNING document_id
        """
        result = self.execute_query(
            query, {"document_id": document_id, "group_id": group_id}
        ).fetchone()

        if not result:
            raise R2RException(
                status_code=404,
                message="Document not found in the specified group"
            )    