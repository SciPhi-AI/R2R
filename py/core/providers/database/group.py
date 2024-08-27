from datetime import datetime
from typing import Optional
from uuid import UUID

from core.base import R2RException
from core.base.abstractions import DocumentInfo, DocumentStatus, DocumentType
from core.base.api.models.auth.responses import UserResponse
from core.base.api.models.management.responses import (
    GroupOverviewResponse,
    GroupResponse,
)

from .base import DatabaseMixin, QueryBuilder


class GroupMixin(DatabaseMixin):
    def create_table(self) -> None:
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('groups')} (
            group_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        self.execute_query(query)

    def group_exists(self, group_id: UUID) -> bool:
        """Check if a group exists."""
        query = f"""
            SELECT 1 FROM {self._get_table_name('groups')}
            WHERE group_id = :group_id
        """
        result = self.execute_query(query, {"group_id": group_id}).fetchone()
        return bool(result)

    def create_group(self, name: str, description: str = "") -> GroupResponse:
        current_time = datetime.utcnow()
        query = f"""
            INSERT INTO {self._get_table_name('groups')} (name, description, created_at, updated_at)
            VALUES (:name, :description, :created_at, :updated_at)
            RETURNING group_id, name, description, created_at, updated_at
        """
        params = {
            "name": name,
            "description": description,
            "created_at": current_time,
            "updated_at": current_time,
        }
        result = self.execute_query(query, params).fetchone()
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

    def get_group(self, group_id: UUID) -> GroupResponse:
        """Get a group by its ID."""
        if not self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            SELECT group_id, name, description, created_at, updated_at
            FROM {self._get_table_name('groups')}
            WHERE group_id = :group_id
        """
        result = self.execute_query(query, {"group_id": group_id}).fetchone()
        return GroupResponse(
            group_id=result[0],
            name=result[1],
            description=result[2],
            created_at=result[3],
            updated_at=result[4],
        )

    def update_group(
        self, group_id: UUID, name: str, description: str
    ) -> GroupResponse:
        """Update an existing group."""
        if not self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('groups')}
            SET name = :name, description = :description, updated_at = NOW()
            WHERE group_id = :group_id
            RETURNING group_id, name, description, created_at, updated_at
        """
        result = self.execute_query(
            query,
            {"group_id": group_id, "name": name, "description": description},
        ).fetchone()
        return GroupResponse(
            group_id=result[0],
            name=result[1],
            description=result[2],
            created_at=result[3],
            updated_at=result[4],
        )

    def delete_group(self, group_id: UUID) -> None:
        # Remove group_id from users
        user_update_query = f"""
            UPDATE {self._get_table_name('users')}
            SET group_ids = array_remove(group_ids, :group_id)
            WHERE :group_id = ANY(group_ids)
        """
        self.execute_query(user_update_query, {"group_id": group_id})

        # Remove group_id from documents in the relational database
        doc_update_query = f"""
            UPDATE {self._get_table_name('document_info')}
            SET group_ids = array_remove(group_ids, :group_id)
            WHERE :group_id = ANY(group_ids)
        """
        self.execute_query(doc_update_query, {"group_id": group_id})

        # Delete the group
        delete_query = f"""
            DELETE FROM {self._get_table_name('groups')}
            WHERE group_id = :group_id
            RETURNING group_id
        """
        result = self.execute_query(
            delete_query, {"group_id": group_id}
        ).fetchone()

        if not result:
            raise R2RException(status_code=404, message="Group not found")

    def list_groups(
        self, offset: int = 0, limit: int = 100
    ) -> list[GroupResponse]:
        """List groups with pagination."""
        query = f"""
            SELECT group_id, name, description, created_at, updated_at
            FROM {self._get_table_name('groups')}
            ORDER BY name
            OFFSET :offset
            LIMIT :limit
        """
        results = self.execute_query(
            query, {"offset": offset, "limit": limit}
        ).fetchall()
        if not results:
            return []
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

    def get_groups_by_ids(self, group_ids: list[UUID]) -> list[GroupResponse]:
        query, params = (
            QueryBuilder(self._get_table_name("groups"))
            .select(
                ["group_id", "name", "description", "created_at", "updated_at"]
            )
            .where("group_id = ANY(:group_ids)", group_ids=group_ids)
            .build()
        )
        results = self.execute_query(query, params).fetchall()
        if len(results) != len(group_ids):
            raise R2RException(
                status_code=404,
                message=f"These groups were not found: {set(group_ids) - set([row[0] for row in results])}",
            )
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

    def add_user_to_group(self, user_id: UUID, group_id: UUID) -> bool:
        """Add a user to a group."""
        if not self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('users')}
            SET group_ids = array_append(group_ids, :group_id)
            WHERE user_id = :user_id AND NOT (:group_id = ANY(group_ids))
            RETURNING user_id
        """
        result = self.execute_query(
            query, {"user_id": user_id, "group_id": group_id}
        ).fetchone()
        return bool(result)

    def remove_user_from_group(self, user_id: UUID, group_id: UUID) -> None:
        """Remove a user from a group."""
        if not self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            UPDATE {self._get_table_name('users')}
            SET group_ids = array_remove(group_ids, :group_id)
            WHERE user_id = :user_id AND :group_id = ANY(group_ids)
            RETURNING user_id
        """
        result = self.execute_query(
            query, {"user_id": user_id, "group_id": group_id}
        ).fetchone()
        if not result:
            raise R2RException(
                status_code=404,
                message="User is not a member of the specified group",
            )

    def get_users_in_group(
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
        if not self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")

        query = f"""
            SELECT u.user_id, u.email, u.is_active, u.is_superuser, u.created_at, u.updated_at,
                   u.is_verified, u.group_ids, u.name, u.bio, u.profile_picture
            FROM {self._get_table_name('users')} u
            WHERE :group_id = ANY(u.group_ids)
            ORDER BY u.name
            OFFSET :offset
            LIMIT :limit
        """
        results = self.execute_query(
            query, {"group_id": group_id, "offset": offset, "limit": limit}
        ).fetchall()

        return [
            UserResponse(
                id=row[0],
                email=row[1],
                is_active=row[2],
                is_superuser=row[3],
                created_at=row[4],
                updated_at=row[5],
                is_verified=row[6],
                group_ids=row[7],
                name=row[8],
                bio=row[9],
                profile_picture=row[10],
                hashed_password=None,
                verification_code_expiry=None,
            )
            for row in results
        ]

    def documents_in_group(
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
        if not self.group_exists(group_id):
            raise R2RException(status_code=404, message="Group not found")
        query = f"""
            SELECT d.document_id, d.user_id, d.type, d.metadata, d.title, d.version, d.size_in_bytes, d.ingestion_status, d.created_at, d.updated_at
            FROM {self._get_table_name('document_info')} d
            WHERE :group_id = ANY(d.group_ids)
            ORDER BY d.created_at DESC
            OFFSET :offset
            LIMIT :limit
        """
        results = self.execute_query(
            query, {"group_id": group_id, "offset": offset, "limit": limit}
        ).fetchall()
        return [
            DocumentInfo(
                id=row[0],
                user_id=row[1],
                type=DocumentType(row[2]),
                metadata=row[3],
                title=row[4],
                version=row[5],
                size_in_bytes=row[6],
                ingestion_status=DocumentStatus(row[7]),
                created_at=row[8],
                updated_at=row[9],
                group_ids=[group_id],
            )
            for row in results
        ]

    def get_groups_overview(
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
        params = {"offset": offset, "limit": limit}
        if group_ids:
            query += " WHERE g.group_id = ANY(:group_ids)"
            params["group_ids"] = group_ids
        query += """
                GROUP BY g.group_id, g.name, g.description, g.created_at, g.updated_at
            )
            SELECT * FROM group_overview
            ORDER BY name
            OFFSET :offset
            LIMIT :limit
        """

        results = self.execute_query(query, params).fetchall()
        if not results:
            return []
        return [
            GroupOverviewResponse(
                group_id=result[0],
                name=result[1],
                description=result[2],
                created_at=result[3],
                updated_at=result[4],
                user_count=result[5],
                document_count=result[6],
            )
            for result in results
        ]

    def get_groups_for_user(
        self, user_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[GroupResponse]:
        query = f"""
            SELECT g.group_id, g.name, g.description, g.created_at, g.updated_at
            FROM {self._get_table_name('groups')} g
            JOIN {self._get_table_name('users')} u ON g.group_id = ANY(u.group_ids)
            WHERE u.user_id = :user_id
            ORDER BY g.name
            OFFSET :offset
            LIMIT :limit
        """
        results = self.execute_query(
            query, {"user_id": user_id, "offset": offset, "limit": limit}
        ).fetchall()

        if not results:
            return []

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

    def assign_document_to_group(
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
            if not self.group_exists(group_id):
                raise R2RException(status_code=404, message="Group not found")

            # First, check if the document exists
            document_check_query = f"""
                SELECT 1 FROM {self._get_table_name('document_info')}
                WHERE document_id = :document_id
            """
            document_exists = self.execute_query(
                document_check_query, {"document_id": document_id}
            ).fetchone()

            if not document_exists:
                raise R2RException(
                    status_code=404, message="Document not found"
                )

            # If document exists, proceed with the assignment
            assign_query = f"""
                UPDATE {self._get_table_name('document_info')}
                SET group_ids = array_append(group_ids, :group_id)
                WHERE document_id = :document_id AND NOT (:group_id = ANY(group_ids))
                RETURNING document_id
            """
            result = self.execute_query(
                assign_query,
                {"document_id": document_id, "group_id": group_id},
            ).fetchone()

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
                message="An error occurred while assigning the document to the group",
            )

    def document_groups(
        self, document_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[GroupResponse]:
        query = f"""
            SELECT g.group_id, g.name, g.description, g.created_at, g.updated_at
            FROM {self._get_table_name('groups')} g
            JOIN {self._get_table_name('document_info')} d ON g.group_id = ANY(d.group_ids)
            WHERE d.document_id = :document_id
            ORDER BY g.name
            OFFSET :offset
            LIMIT :limit
        """
        params = {"document_id": document_id, "offset": offset, "limit": limit}
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

    def remove_document_from_group(
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
                message="Document not found in the specified group",
            )
