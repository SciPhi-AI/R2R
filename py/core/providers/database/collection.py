import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from core.base import R2RException
from core.base.abstractions import DocumentInfo, DocumentType, IngestionStatus
from core.base.api.models.auth.responses import UserResponse
from core.base.api.models.management.responses import (
    GroupOverviewResponse,
    GroupResponse,
)

from .base import DatabaseMixin


class CollectionMixin(DatabaseMixin):
    async def create_table(self) -> None:
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('groups')} (
            collection_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        await self.execute_query(query)

    async def group_exists(self, collection_id: UUID) -> bool:
        """Check if a group exists."""
        query = f"""
            SELECT 1 FROM {self._get_table_name('groups')}
            WHERE collection_id = $1
        """
        result = await self.execute_query(query, [collection_id])
        return bool(result)

    async def create_collection(
        self, name: str, description: str = ""
    ) -> GroupResponse:
        current_time = datetime.utcnow()
        query = f"""
            INSERT INTO {self._get_table_name('groups')} (name, description, created_at, updated_at)
            VALUES ($1, $2, $3, $4)
            RETURNING collection_id, name, description, created_at, updated_at
        """
        params = [name, description, current_time, current_time]

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, *params)

            if not row:
                raise R2RException(
                    status_code=500, message="Failed to create group"
                )

            return GroupResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        except Exception as e:
            raise R2RException(
                status_code=500,
                message=f"An error occurred while creating the group: {str(e)}",
            )

    async def get_collection(self, collection_id: UUID) -> GroupResponse:
        """Get a group by its ID."""
        if not await self.group_exists(collection_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            SELECT collection_id, name, description, created_at, updated_at
            FROM {self._get_table_name('groups')}
            WHERE collection_id = $1
        """
        result = await self.fetchrow_query(query, [collection_id])
        if not result:
            raise R2RException(status_code=404, message="Group not found")

        return GroupResponse(
            collection_id=result["collection_id"],
            name=result["name"],
            description=result["description"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
        )

    async def update_collection(
        self, collection_id: UUID, name: str, description: str
    ) -> GroupResponse:
        """Update an existing group."""
        if not await self.group_exists(collection_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('groups')}
            SET name = $1, description = $2, updated_at = NOW()
            WHERE collection_id = $3
            RETURNING collection_id, name, description, created_at, updated_at
        """
        result = await self.fetchrow_query(
            query, [name, description, collection_id]
        )
        if not result:
            raise R2RException(status_code=404, message="Group not found")

        return GroupResponse(
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

        # Delete the group
        delete_query = f"""
            DELETE FROM {self._get_table_name('groups')}
            WHERE collection_id = $1
        """
        result = await self.execute_query(delete_query, [collection_id])

        if result == "DELETE 0":
            raise R2RException(status_code=404, message="Group not found")

    async def list_collections(
        self, offset: int = 0, limit: int = 100
    ) -> list[GroupResponse]:
        """List groups with pagination."""
        query = f"""
            SELECT collection_id, name, description, created_at, updated_at
            FROM {self._get_table_name('groups')}
            ORDER BY name
            OFFSET $1
            LIMIT $2
        """
        results = await self.fetch_query(query, [offset, limit])
        if not results:
            return []
        return [
            GroupResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]

    async def get_collections_by_ids(
        self, collection_ids: list[UUID]
    ) -> list[GroupResponse]:
        query = f"""
            SELECT collection_id, name, description, created_at, updated_at
            FROM {self._get_table_name("groups")}
            WHERE collection_id = ANY($1)
        """
        results = await self.fetch_query(query, [collection_ids])
        if len(results) != len(collection_ids):
            raise R2RException(
                status_code=404,
                message=f"These groups were not found: {set(collection_ids) - {row['collection_id'] for row in results}}",
            )
        return [
            GroupResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]

    async def add_user_to_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> bool:
        """Add a user to a group."""
        if not await self.group_exists(collection_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('users')}
            SET collection_ids = array_append(collection_ids, $1)
            WHERE user_id = $2 AND NOT ($1 = ANY(collection_ids))
            RETURNING user_id
        """
        result = await self.fetchrow_query(query, [collection_id, user_id])
        return bool(result)

    async def remove_user_from_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> None:
        """Remove a user from a group."""
        if not await self.group_exists(collection_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('users')}
            SET collection_ids = array_remove(collection_ids, $1)
            WHERE user_id = $2 AND $1 = ANY(collection_ids)
            RETURNING user_id
        """
        result = await self.fetchrow_query(query, [collection_id, user_id])
        if not result:
            raise R2RException(
                status_code=404,
                message="User is not a member of the specified collection",
            )

    async def get_users_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[UserResponse]:
        """
        Get all users in a specific group with pagination.

        Args:
            collection_id (UUID): The ID of the group to get users from.
            offset (int): The number of users to skip.
            limit (int): The maximum number of users to return.

        Returns:
            List[UserResponse]: A list of UserResponse objects representing the users in the group.

        Raises:
            R2RException: If the group doesn't exist.
        """
        if not await self.group_exists(collection_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            SELECT u.user_id, u.email, u.is_active, u.is_superuser, u.created_at, u.updated_at,
                u.is_verified, u.collection_ids, u.name, u.bio, u.profile_picture
            FROM {self._get_table_name('users')} u
            WHERE $1 = ANY(u.collection_ids)
            ORDER BY u.name
            OFFSET $2
            LIMIT $3
        """
        results = await self.fetch_query(query, [collection_id, offset, limit])

        return [
            UserResponse(
                id=row["user_id"],
                email=row["email"],
                is_active=row["is_active"],
                is_superuser=row["is_superuser"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                is_verified=row["is_verified"],
                collection_ids=row["collection_ids"],
                name=row["name"],
                bio=row["bio"],
                profile_picture=row["profile_picture"],
                hashed_password=None,
                verification_code_expiry=None,
            )
            for row in results
        ]

    async def documents_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[DocumentInfo]:
        """
        Get all documents in a specific group with pagination.
        Args:
            collection_id (UUID): The ID of the group to get documents from.
            offset (int): The number of documents to skip.
            limit (int): The maximum number of documents to return.
        Returns:
            List[DocumentInfo]: A list of DocumentInfo objects representing the documents in the group.
        Raises:
            R2RException: If the group doesn't exist.
        """
        if not await self.group_exists(collection_id):
            raise R2RException(status_code=404, message="Group not found")
        query = f"""
            SELECT d.document_id, d.user_id, d.type, d.metadata, d.title, d.version, d.size_in_bytes, d.ingestion_status, d.created_at, d.updated_at
            FROM {self._get_table_name('document_info')} d
            WHERE $1 = ANY(d.collection_ids)
            ORDER BY d.created_at DESC
            OFFSET $2
            LIMIT $3
        """
        results = await self.fetch_query(query, [collection_id, offset, limit])
        return [
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

    async def get_collections_overview(
        self,
        collection_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[GroupOverviewResponse]:
        """Get an overview of groups, optionally filtered by group IDs, with pagination."""
        query = f"""
            WITH group_overview AS (
                SELECT g.collection_id, g.name, g.description, g.created_at, g.updated_at,
                    COUNT(DISTINCT u.user_id) AS user_count,
                    COUNT(DISTINCT d.document_id) AS document_count
                FROM {self._get_table_name('groups')} g
                LEFT JOIN {self._get_table_name('users')} u ON g.collection_id = ANY(u.collection_ids)
                LEFT JOIN {self._get_table_name('document_info')} d ON g.collection_id = ANY(d.collection_ids)
        """
        params = []
        if collection_ids:
            query += " WHERE g.collection_id = ANY($1)"
            params.append(collection_ids)

        query += """
                GROUP BY g.collection_id, g.name, g.description, g.created_at, g.updated_at
            )
            SELECT * FROM group_overview
            ORDER BY name
            OFFSET ${} LIMIT ${}
        """.format(
            len(params) + 1, len(params) + 2
        )

        params.extend([offset, limit])

        results = await self.fetch_query(query, params)
        return [
            GroupOverviewResponse(
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

    async def get_collections_for_user(
        self, user_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[GroupResponse]:
        query = f"""
            SELECT g.collection_id, g.name, g.description, g.created_at, g.updated_at
            FROM {self._get_table_name('groups')} g
            JOIN {self._get_table_name('users')} u ON g.collection_id = ANY(u.collection_ids)
            WHERE u.user_id = $1
            ORDER BY g.name
            OFFSET $2
            LIMIT $3
        """
        results = await self.fetch_query(query, [user_id, offset, limit])

        return [
            GroupResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]

    async def assign_document_to_collection(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        """
        Assign a document to a group.

        Args:
            document_id (UUID): The ID of the document to assign.
            collection_id (UUID): The ID of the group to assign the document to.

        Raises:
            R2RException: If the group doesn't exist, if the document is not found,
                        or if there's a database error.
        """
        try:
            if not await self.group_exists(collection_id):
                raise R2RException(status_code=404, message="Group not found")

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
                # Document exists but was already assigned to the group
                raise R2RException(
                    status_code=409,
                    message="Document is already assigned to the group",
                )

        except R2RException:
            # Re-raise R2RExceptions as they are already handled
            raise
        except Exception as e:
            raise R2RException(
                status_code=500,
                message=f"An error '{e}' occurred while assigning the document to the group",
            )

    async def document_collections(
        self, document_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[GroupResponse]:
        query = f"""
            SELECT g.collection_id, g.name, g.description, g.created_at, g.updated_at
            FROM {self._get_table_name('groups')} g
            JOIN {self._get_table_name('document_info')} d ON g.collection_id = ANY(d.collection_ids)
            WHERE d.document_id = $1
            ORDER BY g.name
            OFFSET $2
            LIMIT $3
        """
        results = await self.fetch_query(query, [document_id, offset, limit])

        return [
            GroupResponse(
                collection_id=row["collection_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]

    async def remove_document_from_collection(
        self, document_id: UUID, collection_id: UUID
    ) -> None:
        """
        Remove a document from a group.

        Args:
            document_id (UUID): The ID of the document to remove.
            collection_id (UUID): The ID of the group to remove the document from.

        Raises:
            R2RException: If the group doesn't exist or if the document is not in the group.
        """
        if not await self.group_exists(collection_id):
            raise R2RException(status_code=404, message="Group not found")

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
                message="Document not found in the specified group",
            )
