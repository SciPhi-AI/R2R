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


class GroupMixin(DatabaseMixin):
    async def create_table(self) -> None:
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('groups')} (
            group_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        await self.execute_query(query)

    async def group_exists(self, group_id: UUID) -> bool:
        """Check if a group exists."""
        query = f"""
            SELECT 1 FROM {self._get_table_name('groups')}
            WHERE group_id = $1
        """
        result = await self.execute_query(query, [group_id])
        return bool(result)

    async def create_group(
        self, name: str, description: str = ""
    ) -> GroupResponse:
        current_time = datetime.utcnow()
        query = f"""
            INSERT INTO {self._get_table_name('groups')} (name, description, created_at, updated_at)
            VALUES ($1, $2, $3, $4)
            RETURNING group_id, name, description, created_at, updated_at
        """
        params = [name, description, current_time, current_time]
        result = await self.execute_query(query, params).fetchone()
        if not result:
            raise R2RException(
                status_code=500, message="Failed to create group"
            )

        return GroupResponse(
            group_id=result[0],
            name=result[1],
            description=result[2],
            created_at=result[3],
            updated_at=result[4],
        )

    async def get_group(self, group_id: UUID) -> GroupResponse:
        """Get a group by its ID."""
        if not await self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            SELECT group_id, name, description, created_at, updated_at
            FROM {self._get_table_name('groups')}
            WHERE group_id = $1
        """
        result = await self.fetchrow_query(query, [group_id])
        if not result:
            raise R2RException(status_code=404, message="Group not found")

        return GroupResponse(
            group_id=result["group_id"],
            name=result["name"],
            description=result["description"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
        )

    async def update_group(
        self, group_id: UUID, name: str, description: str
    ) -> GroupResponse:
        """Update an existing group."""
        if not await self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('groups')}
            SET name = $1, description = $2, updated_at = NOW()
            WHERE group_id = $3
            RETURNING group_id, name, description, created_at, updated_at
        """
        result = await self.fetchrow_query(
            query, [name, description, group_id]
        )
        if not result:
            raise R2RException(status_code=404, message="Group not found")

        return GroupResponse(
            group_id=result["group_id"],
            name=result["name"],
            description=result["description"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
        )

    async def delete_group(self, group_id: UUID) -> None:
        # Remove group_id from users
        user_update_query = f"""
            UPDATE {self._get_table_name('users')}
            SET group_ids = array_remove(group_ids, $1)
            WHERE $1 = ANY(group_ids)
        """
        await self.execute_query(user_update_query, [group_id])

        # Delete the group
        delete_query = f"""
            DELETE FROM {self._get_table_name('groups')}
            WHERE group_id = $1
        """
        result = await self.execute_query(delete_query, [group_id])

        if result == "DELETE 0":
            raise R2RException(status_code=404, message="Group not found")

    async def list_groups(
        self, offset: int = 0, limit: int = 100
    ) -> list[GroupResponse]:
        """List groups with pagination."""
        query = f"""
            SELECT group_id, name, description, created_at, updated_at
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
                group_id=row["group_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]

    async def get_groups_by_ids(
        self, group_ids: list[UUID]
    ) -> list[GroupResponse]:
        query = f"""
            SELECT group_id, name, description, created_at, updated_at
            FROM {self._get_table_name("groups")}
            WHERE group_id = ANY($1)
        """
        results = await self.fetch_query(query, [group_ids])
        if len(results) != len(group_ids):
            raise R2RException(
                status_code=404,
                message=f"These groups were not found: {set(group_ids) - {row['group_id'] for row in results}}",
            )
        return [
            GroupResponse(
                group_id=row["group_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]

    async def add_user_to_group(self, user_id: UUID, group_id: UUID) -> bool:
        """Add a user to a group."""
        if not await self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('users')}
            SET group_ids = array_append(group_ids, $1)
            WHERE user_id = $2 AND NOT ($1 = ANY(group_ids))
            RETURNING user_id
        """
        result = await self.fetchrow_query(query, [group_id, user_id])
        return bool(result)

    async def remove_user_from_group(
        self, user_id: UUID, group_id: UUID
    ) -> None:
        """Remove a user from a group."""
        if not await self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('users')}
            SET group_ids = array_remove(group_ids, $1)
            WHERE user_id = $2 AND $1 = ANY(group_ids)
            RETURNING user_id
        """
        result = await self.fetchrow_query(query, [group_id, user_id])
        if not result:
            raise R2RException(
                status_code=404,
                message="User is not a member of the specified group",
            )

    async def get_users_in_group(
        self, group_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[UserResponse]:
        """
        Get all users in a specific group with pagination.

        Args:
            group_id (UUID): The ID of the group to get users from.
            offset (int): The number of users to skip.
            limit (int): The maximum number of users to return.

        Returns:
            List[UserResponse]: A list of UserResponse objects representing the users in the group.

        Raises:
            R2RException: If the group doesn't exist.
        """
        if not await self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            SELECT u.user_id, u.email, u.is_active, u.is_superuser, u.created_at, u.updated_at,
                u.is_verified, u.group_ids, u.name, u.bio, u.profile_picture
            FROM {self._get_table_name('users')} u
            WHERE $1 = ANY(u.group_ids)
            ORDER BY u.name
            OFFSET $2
            LIMIT $3
        """
        results = await self.fetch_query(query, [group_id, offset, limit])

        return [
            UserResponse(
                id=row["user_id"],
                email=row["email"],
                is_active=row["is_active"],
                is_superuser=row["is_superuser"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                is_verified=row["is_verified"],
                group_ids=row["group_ids"],
                name=row["name"],
                bio=row["bio"],
                profile_picture=row["profile_picture"],
                hashed_password=None,
                verification_code_expiry=None,
            )
            for row in results
        ]

    async def documents_in_group(
        self, group_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[DocumentInfo]:
        """
        Get all documents in a specific group with pagination.
        Args:
            group_id (UUID): The ID of the group to get documents from.
            offset (int): The number of documents to skip.
            limit (int): The maximum number of documents to return.
        Returns:
            List[DocumentInfo]: A list of DocumentInfo objects representing the documents in the group.
        Raises:
            R2RException: If the group doesn't exist.
        """
        if not await self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")
        query = f"""
            SELECT d.document_id, d.user_id, d.type, d.metadata, d.title, d.version, d.size_in_bytes, d.ingestion_status, d.created_at, d.updated_at
            FROM {self._get_table_name('document_info')} d
            WHERE $1 = ANY(d.group_ids)
            ORDER BY d.created_at DESC
            OFFSET $2
            LIMIT $3
        """
        results = await self.fetch_query(query, [group_id, offset, limit])
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
                group_ids=[group_id],
            )
            for row in results
        ]

    async def get_groups_overview(
        self,
        group_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[GroupOverviewResponse]:
        """Get an overview of groups, optionally filtered by group IDs, with pagination."""
        query = f"""
            WITH group_overview AS (
                SELECT g.group_id, g.name, g.description, g.created_at, g.updated_at,
                    COUNT(DISTINCT u.user_id) AS user_count,
                    COUNT(DISTINCT d.document_id) AS document_count
                FROM {self._get_table_name('groups')} g
                LEFT JOIN {self._get_table_name('users')} u ON g.group_id = ANY(u.group_ids)
                LEFT JOIN {self._get_table_name('document_info')} d ON g.group_id = ANY(d.group_ids)
        """
        params = []
        if group_ids:
            query += " WHERE g.group_id = ANY($1)"
            params.append(group_ids)

        query += """
                GROUP BY g.group_id, g.name, g.description, g.created_at, g.updated_at
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
                group_id=row["group_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                user_count=row["user_count"],
                document_count=row["document_count"],
            )
            for row in results
        ]

    async def get_groups_for_user(
        self, user_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[GroupResponse]:
        query = f"""
            SELECT g.group_id, g.name, g.description, g.created_at, g.updated_at
            FROM {self._get_table_name('groups')} g
            JOIN {self._get_table_name('users')} u ON g.group_id = ANY(u.group_ids)
            WHERE u.user_id = $1
            ORDER BY g.name
            OFFSET $2
            LIMIT $3
        """
        results = await self.fetch_query(query, [user_id, offset, limit])

        return [
            GroupResponse(
                group_id=row["group_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]

    async def assign_document_to_group(
        self, document_id: UUID, group_id: UUID
    ) -> None:
        """
        Assign a document to a group.

        Args:
            document_id (UUID): The ID of the document to assign.
            group_id (UUID): The ID of the group to assign the document to.

        Raises:
            R2RException: If the group doesn't exist, if the document is not found,
                        or if there's a database error.
        """
        try:
            if not await self.group_exists(group_id):
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
                SET group_ids = array_append(group_ids, $1)
                WHERE document_id = $2 AND NOT ($1 = ANY(group_ids))
                RETURNING document_id
            """
            result = await self.fetchrow_query(
                assign_query, [group_id, document_id]
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

    async def document_groups(
        self, document_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[GroupResponse]:
        query = f"""
            SELECT g.group_id, g.name, g.description, g.created_at, g.updated_at
            FROM {self._get_table_name('groups')} g
            JOIN {self._get_table_name('document_info')} d ON g.group_id = ANY(d.group_ids)
            WHERE d.document_id = $1
            ORDER BY g.name
            OFFSET $2
            LIMIT $3
        """
        results = await self.fetch_query(query, [document_id, offset, limit])

        return [
            GroupResponse(
                group_id=row["group_id"],
                name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in results
        ]

    async def remove_document_from_group(
        self, document_id: UUID, group_id: UUID
    ) -> None:
        """
        Remove a document from a group.

        Args:
            document_id (UUID): The ID of the document to remove.
            group_id (UUID): The ID of the group to remove the document from.

        Raises:
            R2RException: If the group doesn't exist or if the document is not in the group.
        """
        if not await self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('document_info')}
            SET group_ids = array_remove(group_ids, $1)
            WHERE document_id = $2 AND $1 = ANY(group_ids)
            RETURNING document_id
        """
        result = await self.fetchrow_query(query, [group_id, document_id])

        if not result:
            raise R2RException(
                status_code=404,
                message="Document not found in the specified group",
            )
