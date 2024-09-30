import json
import logging
from datetime import datetime
from typing import Optional, Union
from uuid import UUID

from core.base import R2RException
from core.base.abstractions import DocumentInfo, DocumentType, IngestionStatus
from core.base.api.models import CollectionOverviewResponse, CollectionResponse

from .base import DatabaseMixin

logger = logging.getLogger(__name__)


class CollectionMixin(DatabaseMixin):
    async def create_table(self) -> None:
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('collections')} (
            collection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        await self.execute_query(query)

    async def collection_exists(self, collection_id: UUID) -> bool:
        """Check if a collection exists."""
        query = f"""
            SELECT 1 FROM {self._get_table_name('collections')}
            WHERE collection_id = $1
        """
        result = await self.execute_query(query, [collection_id])
        return bool(result)

    async def create_collection(
        self, name: str, description: str = ""
    ) -> CollectionResponse:
        current_time = datetime.utcnow()
        query = f"""
            INSERT INTO {self._get_table_name('collections')} (name, description, created_at, updated_at)
            VALUES ($1, $2, $3, $4)
            RETURNING collection_id, name, description, created_at, updated_at
        """
        params = [name, description, current_time, current_time]

        try:
            async with self.pool.acquire() as conn:  # type: ignore
                row = await conn.fetchrow(query, *params)

            if not row:
                raise R2RException(
                    status_code=500, message="Failed to create collection"
                )

            return CollectionResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        except Exception as e:
            raise R2RException(
                status_code=500,
                message=f"An error occurred while creating the collection: {str(e)}",
            )

    async def get_collection(self, collection_id: UUID) -> CollectionResponse:
        """Get a collection by its ID."""
        if not await self.collection_exists(collection_id):
            raise R2RException(status_code=404, message="Collection not found")

        query = f"""
            SELECT collection_id, name, description, created_at, updated_at
            FROM {self._get_table_name('collections')}
            WHERE collection_id = $1
        """
        result = await self.fetchrow_query(query, [collection_id])
        if not result:
            raise R2RException(status_code=404, message="Collection not found")

        return CollectionResponse(
            collection_id=result["collection_id"],
            name=result["name"],
            description=result["description"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
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
            update_fields.append("description = ${}".format(len(params) + 1))
            params.append(description)

        if not update_fields:
            raise R2RException(status_code=400, message="No fields to update")

        update_fields.append("updated_at = NOW()")
        params.append(collection_id)

        query = f"""
            UPDATE {self._get_table_name('collections')}
            SET {', '.join(update_fields)}
            WHERE collection_id = ${len(params)}
            RETURNING collection_id, name, description, created_at, updated_at
        """

        result = await self.fetchrow_query(query, params)
        if not result:
            raise R2RException(status_code=404, message="Collection not found")

        return CollectionResponse(
            collection_id=result["collection_id"],
            name=result["name"],
            description=result["description"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
        )

    async def delete_collection(self, collection_id: UUID) -> None:
        # Remove collection_id from users
        user_update_query = f"""
            UPDATE {self._get_table_name('users')}
            SET collection_ids = array_remove(collection_ids, $1)
            WHERE $1 = ANY(collection_ids)
        """
        await self.execute_query(user_update_query, [collection_id])

        # Delete the collection
        delete_query = f"""
            DELETE FROM {self._get_table_name('collections')}
            WHERE collection_id = $1
        """
        result = await self.execute_query(delete_query, [collection_id])

        if result == "DELETE 0":
            raise R2RException(status_code=404, message="Collection not found")

    async def list_collections(
        self, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[CollectionResponse], int]]:
        """List collections with pagination."""
        query = f"""
            SELECT collection_id, name, description, created_at, updated_at, COUNT(*) OVER() AS total_entries
            FROM {self._get_table_name('collections')}
            ORDER BY name
            OFFSET $1
        """

        conditions = [offset]
        if limit != -1:
            query += " LIMIT $2"
            conditions.append(limit)

        results = await self.fetch_query(query, conditions)
        if not results:
            logger.info("No collections found.")
            return {"results": [], "total_entries": 0}

        collections = [
            CollectionResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]
        total_entries = results[0]["total_entries"] if results else 0

        return {"results": collections, "total_entries": total_entries}

    async def get_collections_by_ids(
        self, collection_ids: list[UUID]
    ) -> list[CollectionResponse]:
        query = f"""
            SELECT collection_id, name, description, created_at, updated_at
            FROM {self._get_table_name("collections")}
            WHERE collection_id = ANY($1)
        """
        results = await self.fetch_query(query, [collection_ids])
        if len(results) != len(collection_ids):
            raise R2RException(
                status_code=404,
                message=f"These collections were not found: {set(collection_ids) - {row['collection_id'] for row in results}}",
            )
        return [
            CollectionResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]

    async def documents_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[DocumentInfo], int]]:
        """
        Get all documents in a specific collection with pagination.
        Args:
            collection_id (UUID): The ID of the collection to get documents from.
            offset (int): The number of documents to skip.
            limit (int): The maximum number of documents to return.
        Returns:
            List[DocumentInfo]: A list of DocumentInfo objects representing the documents in the collection.
        Raises:
            R2RException: If the collection doesn't exist.
        """
        if not await self.collection_exists(collection_id):
            raise R2RException(status_code=404, message="Collection not found")
        query = f"""
            SELECT d.document_id, d.user_id, d.type, d.metadata, d.title, d.version, d.size_in_bytes, d.ingestion_status, d.created_at, d.updated_at, COUNT(*) OVER() AS total_entries
            FROM {self._get_table_name('document_info')} d
            WHERE $1 = ANY(d.collection_ids)
            ORDER BY d.created_at DESC
            OFFSET $2
        """

        conditions = [collection_id, offset]
        if limit != -1:
            query += " LIMIT $3"
            conditions.append(limit)

        results = await self.fetch_query(query, conditions)
        documents = [
            DocumentInfo(
                id=row["document_id"],
                user_id=row["user_id"],
                type=DocumentType(row["type"]),
                metadata=json.loads(row["metadata"]),
                title=row["title"],
                version=row["version"],
                size_in_bytes=row["size_in_bytes"],
                ingestion_status=IngestionStatus(row["ingestion_status"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                collection_ids=[collection_id],
            )
            for row in results
        ]
        total_entries = results[0]["total_entries"] if results else 0

        return {"results": documents, "total_entries": total_entries}

    async def get_collections_overview(
        self,
        collection_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = -1,
    ) -> dict[str, Union[list[CollectionOverviewResponse], int]]:
        """Get an overview of collections, optionally filtered by collection IDs, with pagination."""
        query = f"""
            WITH collection_overview AS (
                SELECT g.collection_id, g.name, g.description, g.created_at, g.updated_at,
                    COUNT(DISTINCT u.user_id) AS user_count,
                    COUNT(DISTINCT d.document_id) AS document_count
                FROM {self._get_table_name('collections')} g
                LEFT JOIN {self._get_table_name('users')} u ON g.collection_id = ANY(u.collection_ids)
                LEFT JOIN {self._get_table_name('document_info')} d ON g.collection_id = ANY(d.collection_ids)
                {' WHERE g.collection_id = ANY($1)' if collection_ids else ''}
                GROUP BY g.collection_id, g.name, g.description, g.created_at, g.updated_at
            ),
            counted_overview AS (
                SELECT *, COUNT(*) OVER() AS total_entries
                FROM collection_overview
            )
            SELECT * FROM counted_overview
            ORDER BY name
            OFFSET ${2 if collection_ids else 1}
            {f'LIMIT ${3 if collection_ids else 2}' if limit != -1 else ''}
        """

        params: list = []
        if collection_ids:
            params.append(collection_ids)
        params.append(offset)
        if limit != -1:
            params.append(limit)

        results = await self.fetch_query(query, params)

        if not results:
            logger.info("No collections found.")
            return {"results": [], "total_entries": 0}

        collections = [
            CollectionOverviewResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                user_count=row["user_count"],
                document_count=row["document_count"],
            )
            for row in results
        ]

        total_entries = results[0]["total_entries"] if results else 0

        return {"results": collections, "total_entries": total_entries}

    async def get_collections_for_user(
        self, user_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[CollectionResponse], int]]:
        query = f"""
            SELECT g.collection_id, g.name, g.description, g.created_at, g.updated_at, COUNT(*) OVER() AS total_entries
            FROM {self._get_table_name('collections')} g
            JOIN {self._get_table_name('users')} u ON g.collection_id = ANY(u.collection_ids)
            WHERE u.user_id = $1
            ORDER BY g.name
            OFFSET $2
        """

        params = [user_id, offset]
        if limit != -1:
            query += " LIMIT $3"
            params.append(limit)

        results = await self.fetch_query(query, params)

        collections = [
            CollectionResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]
        total_entries = results[0]["total_entries"] if results else 0

        return {"results": collections, "total_entries": total_entries}

    async def assign_document_to_collection(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
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
            document_exists = await self.fetchrow_query(
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
            result = await self.fetchrow_query(
                assign_query, [collection_id, document_id]
            )

            if not result:
                # Document exists but was already assigned to the collection
                raise R2RException(
                    status_code=409,
                    message="Document is already assigned to the collection",
                )

        except R2RException:
            # Re-raise R2RExceptions as they are already handled
            raise
        except Exception as e:
            raise R2RException(
                status_code=500,
                message=f"An error '{e}' occurred while assigning the document to the collection",
            )

    async def document_collections(
        self, document_id: UUID, offset: int = 0, limit: int = -1
    ) -> dict[str, Union[list[CollectionResponse], int]]:
        query = f"""
            SELECT g.collection_id, g.name, g.description, g.created_at, g.updated_at, COUNT(*) OVER() AS total_entries
            FROM {self._get_table_name('collections')} g
            JOIN {self._get_table_name('document_info')} d ON g.collection_id = ANY(d.collection_ids)
            WHERE d.document_id = $1
            ORDER BY g.name
            OFFSET $2
        """

        conditions: list = [document_id, offset]
        if limit != -1:
            query += " LIMIT $3"
            conditions.append(limit)

        results = await self.fetch_query(query, conditions)

        collections = [
            CollectionResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]

        total_entries = results[0]["total_entries"] if results else 0

        return {"results": collections, "total_entries": total_entries}

    async def remove_document_from_collection(
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
        result = await self.fetchrow_query(query, [collection_id, document_id])

        if not result:
            raise R2RException(
                status_code=404,
                message="Document not found in the specified collection",
            )
