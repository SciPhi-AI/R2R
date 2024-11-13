import json
import logging
from typing import Any, Optional
from uuid import UUID, uuid4
from fastapi import HTTPException
from asyncpg.exceptions import UniqueViolationError

from core.base import (
    CollectionHandler,
    DatabaseConfig,
    KGExtractionStatus,
    R2RException,
    generate_default_user_collection_id,
)
from core.base.abstractions import (
    DocumentResponse,
    DocumentType,
    IngestionStatus,
)
from core.base.api.models import CollectionResponse
from core.utils import (
    generate_default_user_collection_id,
)

from .base import PostgresConnectionManager

logger = logging.getLogger()


class PostgresCollectionHandler(CollectionHandler):
    TABLE_NAME = "collections"

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        config: DatabaseConfig,
    ):
        self.config = config
        super().__init__(project_name, connection_manager)

    # TODO: Need to add user_id in migration script
    async def create_tables(self) -> None:
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresCollectionHandler.TABLE_NAME)} (
            collection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID,
            name TEXT NOT NULL,
            description TEXT,
            kg_enrichment_status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        await self.connection_manager.execute_query(query)

    async def collection_exists(self, collection_id: UUID) -> bool:
        """Check if a collection exists."""
        query = f"""
            SELECT 1 FROM {self._get_table_name(PostgresCollectionHandler.TABLE_NAME)}
            WHERE collection_id = $1
        """
        result = await self.connection_manager.fetchrow_query(
            query, [collection_id]
        )
        return result is not None

    async def create_collection(
        self,
        user_id: UUID,
        name: Optional[str] = None,
        description: str = "",
        collection_id: Optional[UUID] = None,
    ) -> CollectionResponse:
        if not name and not collection_id:
            name = self.config.default_collection_name
            collection_id = generate_default_user_collection_id(user_id)

        query = f"""
            INSERT INTO {self._get_table_name(PostgresCollectionHandler.TABLE_NAME)}
            (collection_id, user_id, name, description)
            VALUES ($1, $2, $3, $4)
            RETURNING collection_id, user_id, name, description, kg_enrichment_status, created_at, updated_at
        """
        params = [
            collection_id or uuid4(),
            user_id,
            name,
            description,
        ]

        try:
            result = await self.connection_manager.fetchrow_query(
                query, params
            )
            if not result:
                raise R2RException(
                    status_code=404, message="Collection not found"
                )

            return CollectionResponse(
                collection_id=result["collection_id"],
                user_id=result["user_id"],
                name=result["name"],
                description=result["description"],
                kg_enrichment_status=result["kg_enrichment_status"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
                user_count=0,
                document_count=0,
            )
        except UniqueViolationError:
            raise R2RException(
                status_code=409,
                message="Collection with this ID already exists",
            )

    async def update_collection(
        self,
        collection_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> CollectionResponse:
        """Update an existing collection."""
        if not await self.collection_exists(collection_id):
            raise R2RException(status_code=404, message="Collection not found")

        update_fields = []
        params: list = []

        if name is not None:
            update_fields.append("name = $1")
            params.append(name)

        if description is not None:
            update_fields.append(f"description = ${len(params) + 1}")
            params.append(description)

        if not update_fields:
            raise R2RException(status_code=400, message="No fields to update")

        update_fields.append("updated_at = NOW()")
        params.append(collection_id)

        query = f"""
            WITH updated_collection AS (
                UPDATE {self._get_table_name(PostgresCollectionHandler.TABLE_NAME)}
                SET {', '.join(update_fields)}
                WHERE collection_id = ${len(params)}
                RETURNING collection_id, user_id, name, description, kg_enrichment_status, created_at, updated_at
            )
            SELECT
                uc.*,
                COUNT(DISTINCT u.user_id) FILTER (WHERE u.user_id IS NOT NULL) as user_count,
                COUNT(DISTINCT d.document_id) FILTER (WHERE d.document_id IS NOT NULL) as document_count
            FROM updated_collection uc
            LEFT JOIN {self._get_table_name('users')} u ON uc.collection_id = ANY(u.collection_ids)
            LEFT JOIN {self._get_table_name('document_info')} d ON uc.collection_id = ANY(d.collection_ids)
            GROUP BY uc.collection_id, uc.user_id, uc.name, uc.description, uc.kg_enrichment_status, uc.created_at, uc.updated_at
        """

        result = await self.connection_manager.fetchrow_query(query, params)
        if not result:
            raise R2RException(status_code=404, message="Collection not found")

        return CollectionResponse(
            collection_id=result["collection_id"],
            user_id=result["user_id"],
            name=result["name"],
            description=result["description"],
            kg_enrichment_status=result["kg_enrichment_status"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            user_count=result["user_count"],
            document_count=result["document_count"],
        )

    async def delete_collection_relational(self, collection_id: UUID) -> None:
        # async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
        #     async with conn.transaction():
        #         try:
        # Remove collection_id from users
        user_update_query = f"""
            UPDATE {self._get_table_name('users')}
            SET collection_ids = array_remove(collection_ids, $1)
            WHERE $1 = ANY(collection_ids)
        """
        await self.connection_manager.execute_query(
            user_update_query, [collection_id]
        )

        # Remove collection_id from documents
        document_update_query = f"""
            WITH updated AS (
                UPDATE {self._get_table_name('document_info')}
                SET collection_ids = array_remove(collection_ids, $1)
                WHERE $1 = ANY(collection_ids)
                RETURNING 1
            )
            SELECT COUNT(*) AS affected_rows FROM updated
        """
        await self.connection_manager.fetchrow_query(
            document_update_query, [collection_id]
        )

        # Delete the collection
        delete_query = f"""
            DELETE FROM {self._get_table_name(PostgresCollectionHandler.TABLE_NAME)}
            WHERE collection_id = $1
            RETURNING collection_id
        """
        deleted = await self.connection_manager.fetchrow_query(
            delete_query, [collection_id]
        )

        if not deleted:
            raise R2RException(status_code=404, message="Collection not found")

    async def documents_in_collection(
        self, collection_id: UUID, offset: int, limit: int
    ) -> dict[str, list[DocumentResponse] | int]:
        """
        Get all documents in a specific collection with pagination.
        Args:
            collection_id (UUID): The ID of the collection to get documents from.
            offset (int): The number of documents to skip.
            limit (int): The maximum number of documents to return.
        Returns:
            List[DocumentResponse]: A list of DocumentResponse objects representing the documents in the collection.
        Raises:
            R2RException: If the collection doesn't exist.
        """
        if not await self.collection_exists(collection_id):
            raise R2RException(status_code=404, message="Collection not found")
        query = f"""
            SELECT d.document_id, d.user_id, d.type, d.metadata, d.title, d.version,
                d.size_in_bytes, d.ingestion_status, d.kg_extraction_status, d.created_at, d.updated_at,
                COUNT(*) OVER() AS total_entries
            FROM {self._get_table_name('document_info')} d
            WHERE $1 = ANY(d.collection_ids)
            ORDER BY d.created_at DESC
            OFFSET $2
        """

        conditions = [collection_id, offset]
        if limit != -1:
            query += " LIMIT $3"
            conditions.append(limit)

        results = await self.connection_manager.fetch_query(query, conditions)
        documents = [
            DocumentResponse(
                id=row["document_id"],
                collection_ids=[collection_id],
                user_id=row["user_id"],
                document_type=DocumentType(row["type"]),
                metadata=json.loads(row["metadata"]),
                title=row["title"],
                version=row["version"],
                size_in_bytes=row["size_in_bytes"],
                ingestion_status=IngestionStatus(row["ingestion_status"]),
                kg_extraction_status=KGExtractionStatus(
                    row["kg_extraction_status"]
                ),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]
        total_entries = results[0]["total_entries"] if results else 0

        return {"results": documents, "total_entries": total_entries}

    async def get_collections_overview(
        self,
        offset: int,
        limit: int,
        filter_user_ids: Optional[list[UUID]] = None,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_collection_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[CollectionResponse] | int]:
        conditions = []
        params: list[Any] = []
        param_index = 1

        # Build JOIN clauses based on filters
        document_join = "JOIN" if filter_document_ids else "LEFT JOIN"
        user_join = "JOIN" if filter_user_ids else "LEFT JOIN"

        if filter_user_ids:
            conditions.append(f"u.user_id = ANY(${param_index})")
            params.append(filter_user_ids)
            param_index += 1

        if filter_document_ids:
            conditions.append(f"d.document_id = ANY(${param_index})")
            params.append(filter_document_ids)
            param_index += 1

        if filter_collection_ids:
            conditions.append(f"c.collection_id = ANY(${param_index})")
            params.append(filter_collection_ids)
            param_index += 1

        where_clause = (
            f"WHERE {' AND '.join(conditions)}" if conditions else ""
        )

        query = f"""
            WITH collection_stats AS (
                SELECT
                    c.collection_id,
                    c.user_id,
                    c.name,
                    c.description,
                    c.created_at,
                    c.updated_at,
                    c.kg_enrichment_status,
                    COUNT(DISTINCT u.user_id) FILTER (WHERE u.user_id IS NOT NULL) as user_count,
                    COUNT(DISTINCT d.document_id) FILTER (WHERE d.document_id IS NOT NULL) as document_count
                FROM {self._get_table_name(PostgresCollectionHandler.TABLE_NAME)} c
                {user_join} {self._get_table_name('users')} u ON c.collection_id = ANY(u.collection_ids)
                {document_join} {self._get_table_name('document_info')} d ON c.collection_id = ANY(d.collection_ids)
                {where_clause}
                GROUP BY c.collection_id, c.user_id, c.name, c.description, c.created_at, c.updated_at, c.kg_enrichment_status
            )
            SELECT
                *,
                COUNT(*) OVER() AS total_entries
            FROM collection_stats
            ORDER BY created_at DESC
            OFFSET ${param_index}
        """
        params.append(offset)
        param_index += 1

        if limit != -1:
            query += f" LIMIT ${param_index}"
            params.append(limit)

        try:
            results = await self.connection_manager.fetch_query(query, params)
            if not results:
                return {"results": [], "total_entries": 0}

            total_entries = results[0]["total_entries"] if results else 0

            collections = [
                CollectionResponse(
                    collection_id=row["collection_id"],
                    user_id=row["user_id"],
                    name=row["name"],
                    description=row["description"],
                    kg_enrichment_status=row["kg_enrichment_status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    user_count=row["user_count"],
                    document_count=row["document_count"],
                )
                for row in results
            ]

            return {"results": collections, "total_entries": total_entries}
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while fetching collections: {e}",
            )

    async def assign_document_to_collection_relational(
        self,
        document_id: UUID,
        collection_id: UUID,
    ) -> UUID:
        """
        Assign a document to a collection.

        Args:
            document_id (UUID): The ID of the document to assign.
            collection_id (UUID): The ID of the collection to assign the document to.

        Raises:
            R2RException: If the collection doesn't exist, if the document is not found,
                        or if there's a database error.
        """
        try:
            if not await self.collection_exists(collection_id):
                raise R2RException(
                    status_code=404, message="Collection not found"
                )

            # First, check if the document exists
            document_check_query = f"""
                SELECT 1 FROM {self._get_table_name('document_info')}
                WHERE document_id = $1
            """
            document_exists = await self.connection_manager.fetchrow_query(
                document_check_query, [document_id]
            )

            if not document_exists:
                raise R2RException(
                    status_code=404, message="Document not found"
                )

            # If document exists, proceed with the assignment
            assign_query = f"""
                UPDATE {self._get_table_name('document_info')}
                SET collection_ids = array_append(collection_ids, $1)
                WHERE document_id = $2 AND NOT ($1 = ANY(collection_ids))
                RETURNING document_id
            """
            result = await self.connection_manager.fetchrow_query(
                assign_query, [collection_id, document_id]
            )

            if not result:
                # Document exists but was already assigned to the collection
                raise R2RException(
                    status_code=409,
                    message="Document is already assigned to the collection",
                )

            return collection_id

        except R2RException:
            # Re-raise R2RExceptions as they are already handled
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error '{e}' occurred while assigning the document to the collection",
            )

    async def remove_document_from_collection_relational(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        """
        Remove a document from a collection.

        Args:
            document_id (UUID): The ID of the document to remove.
            collection_id (UUID): The ID of the collection to remove the document from.

        Raises:
            R2RException: If the collection doesn't exist or if the document is not in the collection.
        """
        if not await self.collection_exists(collection_id):
            raise R2RException(status_code=404, message="Collection not found")

        query = f"""
            UPDATE {self._get_table_name('document_info')}
            SET collection_ids = array_remove(collection_ids, $1)
            WHERE document_id = $2 AND $1 = ANY(collection_ids)
            RETURNING document_id
        """
        result = await self.connection_manager.fetchrow_query(
            query, [collection_id, document_id]
        )

        if not result:
            raise R2RException(
                status_code=404,
                message="Document not found in the specified collection",
            )
