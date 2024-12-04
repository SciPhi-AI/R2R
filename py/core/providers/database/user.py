from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import HTTPException

from core.base import CryptoProvider, UserHandler
from core.base.abstractions import R2RException
from core.utils import generate_user_id
from shared.abstractions import User

from .base import PostgresConnectionManager, QueryBuilder
from .collection import PostgresCollectionHandler


class PostgresUserHandler(UserHandler):
    TABLE_NAME = "users"

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        crypto_provider: CryptoProvider,
    ):
        super().__init__(project_name, connection_manager)
        self.crypto_provider = crypto_provider

    async def create_tables(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresUserHandler.TABLE_NAME)} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            is_superuser BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            is_verified BOOLEAN DEFAULT FALSE,
            verification_code TEXT,
            verification_code_expiry TIMESTAMPTZ,
            name TEXT,
            bio TEXT,
            profile_picture TEXT,
            reset_token TEXT,
            reset_token_expiry TIMESTAMPTZ,
            collection_ids UUID[] NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        await self.connection_manager.execute_query(query)

    async def get_user_by_id(self, id: UUID) -> User:
        query, _ = (
            QueryBuilder(self._get_table_name("users"))
            .select(
                [
                    "id",
                    "email",
                    "hashed_password",
                    "is_superuser",
                    "is_active",
                    "is_verified",
                    "created_at",
                    "updated_at",
                    "name",
                    "profile_picture",
                    "bio",
                    "collection_ids",
                ]
            )
            .where("id = $1")
            .build()
        )
        result = await self.connection_manager.fetchrow_query(query, [id])

        if not result:
            raise R2RException(status_code=404, message="User not found")

        return User(
            id=result["id"],
            email=result["email"],
            hashed_password=result["hashed_password"],
            is_superuser=result["is_superuser"],
            is_active=result["is_active"],
            is_verified=result["is_verified"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            name=result["name"],
            profile_picture=result["profile_picture"],
            bio=result["bio"],
            collection_ids=result["collection_ids"],
        )

    async def get_user_by_email(self, email: str) -> User:
        query, params = (
            QueryBuilder(self._get_table_name("users"))
            .select(
                [
                    "id",
                    "email",
                    "hashed_password",
                    "is_superuser",
                    "is_active",
                    "is_verified",
                    "created_at",
                    "updated_at",
                    "name",
                    "profile_picture",
                    "bio",
                    "collection_ids",
                ]
            )
            .where("email = $1")
            .build()
        )
        result = await self.connection_manager.fetchrow_query(query, [email])
        if not result:
            raise R2RException(status_code=404, message="User not found")

        return User(
            id=result["id"],
            email=result["email"],
            hashed_password=result["hashed_password"],
            is_superuser=result["is_superuser"],
            is_active=result["is_active"],
            is_verified=result["is_verified"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            name=result["name"],
            profile_picture=result["profile_picture"],
            bio=result["bio"],
            collection_ids=result["collection_ids"],
        )

    async def create_user(
        self, email: str, password: str, is_superuser: bool = False
    ) -> User:
        try:
            if await self.get_user_by_email(email):
                raise R2RException(
                    status_code=400,
                    message="User with this email already exists",
                )
        except R2RException as e:
            if e.status_code != 404:
                raise e

        hashed_password = self.crypto_provider.get_password_hash(password)  # type: ignore
        query = f"""
            INSERT INTO {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            (email, id, is_superuser, hashed_password, collection_ids)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, email, is_superuser, is_active, is_verified, created_at, updated_at, collection_ids
        """
        result = await self.connection_manager.fetchrow_query(
            query,
            [
                email,
                generate_user_id(email),
                is_superuser,
                hashed_password,
                [],
            ],
        )

        if not result:
            raise HTTPException(
                status_code=500,
                detail="Failed to create user",
            )

        return User(
            id=result["id"],
            email=result["email"],
            is_superuser=result["is_superuser"],
            is_active=result["is_active"],
            is_verified=result["is_verified"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            collection_ids=result["collection_ids"],
            hashed_password=hashed_password,
        )

    async def update_user(self, user: User) -> User:
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET email = $1, is_superuser = $2, is_active = $3, is_verified = $4, updated_at = NOW(),
                name = $5, profile_picture = $6, bio = $7, collection_ids = $8
            WHERE id = $9
            RETURNING id, email, is_superuser, is_active, is_verified, created_at, updated_at, name, profile_picture, bio, collection_ids
        """
        result = await self.connection_manager.fetchrow_query(
            query,
            [
                user.email,
                user.is_superuser,
                user.is_active,
                user.is_verified,
                user.name,
                user.profile_picture,
                user.bio,
                user.collection_ids,
                user.id,
            ],
        )

        if not result:
            raise HTTPException(
                status_code=500,
                detail="Failed to update user",
            )

        return User(
            id=result["id"],
            email=result["email"],
            is_superuser=result["is_superuser"],
            is_active=result["is_active"],
            is_verified=result["is_verified"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            name=result["name"],
            profile_picture=result["profile_picture"],
            bio=result["bio"],
            collection_ids=result["collection_ids"],
        )

    async def delete_user_relational(self, id: UUID) -> None:
        # Get the collections the user belongs to
        collection_query = f"""
            SELECT collection_ids FROM {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            WHERE id = $1
        """
        collection_result = await self.connection_manager.fetchrow_query(
            collection_query, [id]
        )

        if not collection_result:
            raise R2RException(status_code=404, message="User not found")

        # Remove user from documents
        doc_update_query = f"""
            UPDATE {self._get_table_name('documents')}
            SET id = NULL
            WHERE id = $1
        """
        await self.connection_manager.execute_query(doc_update_query, [id])

        # Delete the user
        delete_query = f"""
            DELETE FROM {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            WHERE id = $1
            RETURNING id
        """
        result = await self.connection_manager.fetchrow_query(
            delete_query, [id]
        )

        if not result:
            raise R2RException(status_code=404, message="User not found")

    async def update_user_password(self, id: UUID, new_hashed_password: str):
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET hashed_password = $1, updated_at = NOW()
            WHERE id = $2
        """
        await self.connection_manager.execute_query(
            query, [new_hashed_password, id]
        )

    async def get_all_users(self) -> list[User]:
        query = f"""
            SELECT id, email, is_superuser, is_active, is_verified, created_at, updated_at, collection_ids
            FROM {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
        """
        results = await self.connection_manager.fetch_query(query)

        return [
            User(
                id=result["id"],
                email=result["email"],
                hashed_password="null",
                is_superuser=result["is_superuser"],
                is_active=result["is_active"],
                is_verified=result["is_verified"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
                collection_ids=result["collection_ids"],
            )
            for result in results
        ]

    async def store_verification_code(
        self, id: UUID, verification_code: str, expiry: datetime
    ):
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET verification_code = $1, verification_code_expiry = $2
            WHERE id = $3
        """
        await self.connection_manager.execute_query(
            query, [verification_code, expiry, id]
        )

    async def verify_user(self, verification_code: str) -> None:
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET is_verified = TRUE, verification_code = NULL, verification_code_expiry = NULL
            WHERE verification_code = $1 AND verification_code_expiry > NOW()
            RETURNING id
        """
        result = await self.connection_manager.fetchrow_query(
            query, [verification_code]
        )

        if not result:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

    async def remove_verification_code(self, verification_code: str):
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET verification_code = NULL, verification_code_expiry = NULL
            WHERE verification_code = $1
        """
        await self.connection_manager.execute_query(query, [verification_code])

    async def expire_verification_code(self, id: UUID):
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET verification_code_expiry = NOW() - INTERVAL '1 day'
            WHERE id = $1
        """
        await self.connection_manager.execute_query(query, [id])

    async def store_reset_token(
        self, id: UUID, reset_token: str, expiry: datetime
    ):
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET reset_token = $1, reset_token_expiry = $2
            WHERE id = $3
        """
        await self.connection_manager.execute_query(
            query, [reset_token, expiry, id]
        )

    async def get_user_id_by_reset_token(
        self, reset_token: str
    ) -> Optional[UUID]:
        query = f"""
            SELECT id FROM {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            WHERE reset_token = $1 AND reset_token_expiry > NOW()
        """
        result = await self.connection_manager.fetchrow_query(
            query, [reset_token]
        )
        return result["id"] if result else None

    async def remove_reset_token(self, id: UUID):
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET reset_token = NULL, reset_token_expiry = NULL
            WHERE id = $1
        """
        await self.connection_manager.execute_query(query, [id])

    async def remove_user_from_all_collections(self, id: UUID):
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET collection_ids = ARRAY[]::UUID[]
            WHERE id = $1
        """
        await self.connection_manager.execute_query(query, [id])

    async def add_user_to_collection(
        self, id: UUID, collection_id: UUID
    ) -> bool:
        if not await self.get_user_by_id(id):
            raise R2RException(status_code=404, message="User not found")

        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET collection_ids = array_append(collection_ids, $1)
            WHERE id = $2 AND NOT ($1 = ANY(collection_ids))
            RETURNING id
        """
        result = await self.connection_manager.fetchrow_query(
            query, [collection_id, id]
        )  # fetchrow instead of execute_query
        if not result:
            raise R2RException(
                status_code=400, message="User already in collection"
            )
        return True

    async def remove_user_from_collection(
        self, id: UUID, collection_id: UUID
    ) -> bool:
        if not await self.get_user_by_id(id):
            raise R2RException(status_code=404, message="User not found")

        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET collection_ids = array_remove(collection_ids, $1)
            WHERE id = $2 AND $1 = ANY(collection_ids)
            RETURNING id
        """
        result = await self.connection_manager.fetchrow_query(
            query, [collection_id, id]
        )
        if not result:
            raise R2RException(
                status_code=400,
                message="User is not a member of the specified collection",
            )
        return True

    async def get_users_in_collection(
        self, collection_id: UUID, offset: int, limit: int
    ) -> dict[str, list[User] | int]:
        """
        Get all users in a specific collection with pagination.

        Args:
            collection_id (UUID): The ID of the collection to get users from.
            offset (int): The number of users to skip.
            limit (int): The maximum number of users to return.

        Returns:
            List[User]: A list of User objects representing the users in the collection.

        Raises:
            R2RException: If the collection doesn't exist.
        """
        if not await self._collection_exists(collection_id):  # type: ignore
            raise R2RException(status_code=404, message="Collection not found")

        query = f"""
            SELECT u.id, u.email, u.is_active, u.is_superuser, u.created_at, u.updated_at,
                u.is_verified, u.collection_ids, u.name, u.bio, u.profile_picture,
                COUNT(*) OVER() AS total_entries
            FROM {self._get_table_name(PostgresUserHandler.TABLE_NAME)} u
            WHERE $1 = ANY(u.collection_ids)
            ORDER BY u.name
            OFFSET $2
        """

        conditions = [collection_id, offset]
        if limit != -1:
            query += " LIMIT $3"
            conditions.append(limit)

        results = await self.connection_manager.fetch_query(query, conditions)

        users = [
            User(
                id=row["id"],
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

        total_entries = results[0]["total_entries"] if results else 0

        return {"results": users, "total_entries": total_entries}

    async def mark_user_as_superuser(self, id: UUID):
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET is_superuser = TRUE, is_verified = TRUE, verification_code = NULL, verification_code_expiry = NULL
            WHERE id = $1
        """
        await self.connection_manager.execute_query(query, [id])

    async def get_user_id_by_verification_code(
        self, verification_code: str
    ) -> Optional[UUID]:
        query = f"""
            SELECT id FROM {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            WHERE verification_code = $1 AND verification_code_expiry > NOW()
        """
        result = await self.connection_manager.fetchrow_query(
            query, [verification_code]
        )

        if not result:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

        return result["id"]

    async def mark_user_as_verified(self, id: UUID):
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET is_verified = TRUE, verification_code = NULL, verification_code_expiry = NULL
            WHERE id = $1
        """
        await self.connection_manager.execute_query(query, [id])

    async def get_users_overview(
        self,
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[User] | int]:

        query = f"""
            WITH user_document_ids AS (
                SELECT
                    u.id as user_id,
                    ARRAY_AGG(d.id) FILTER (WHERE d.id IS NOT NULL) AS doc_ids
                FROM {self._get_table_name(PostgresUserHandler.TABLE_NAME)} u
                LEFT JOIN {self._get_table_name('documents')} d ON u.id = d.owner_id
                GROUP BY u.id
            ),
            user_docs AS (
                SELECT
                    u.id,
                    u.email,
                    u.is_superuser,
                    u.is_active,
                    u.is_verified,
                    u.created_at,
                    u.updated_at,
                    u.collection_ids,
                    COUNT(d.id) AS num_files,
                    COALESCE(SUM(d.size_in_bytes), 0) AS total_size_in_bytes,
                    ud.doc_ids as document_ids
                FROM {self._get_table_name(PostgresUserHandler.TABLE_NAME)} u
                LEFT JOIN {self._get_table_name('documents')} d ON u.id = d.owner_id
                LEFT JOIN user_document_ids ud ON u.id = ud.user_id
                {' WHERE u.id = ANY($3::uuid[])' if user_ids else ''}
                GROUP BY u.id, u.email, u.is_superuser, u.is_active, u.is_verified,
                         u.created_at, u.updated_at, u.collection_ids, ud.doc_ids
            )
            SELECT
                user_docs.*,
                COUNT(*) OVER() AS total_entries
            FROM user_docs
            ORDER BY email
            OFFSET $1
        """

        params: list = [offset]

        if limit != -1:
            query += " LIMIT $2"
            params.append(limit)

        if user_ids:
            params.append(user_ids)

        results = await self.connection_manager.fetch_query(query, params)

        users = [
            User(
                id=row["id"],
                email=row["email"],
                is_superuser=row["is_superuser"],
                is_active=row["is_active"],
                is_verified=row["is_verified"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                collection_ids=row["collection_ids"] or [],
                num_files=row["num_files"],
                total_size_in_bytes=row["total_size_in_bytes"],
                document_ids=(
                    []
                    if row["document_ids"] is None
                    else [doc_id for doc_id in row["document_ids"]]
                ),
            )
            for row in results
        ]

        if not users:
            raise R2RException(status_code=404, message="No users found")

        total_entries = results[0]["total_entries"]

        return {"results": users, "total_entries": total_entries}

    async def _collection_exists(self, collection_id: UUID) -> bool:
        """Check if a collection exists."""
        query = f"""
            SELECT 1 FROM {self._get_table_name(PostgresCollectionHandler.TABLE_NAME)}
            WHERE id = $1
        """
        result = await self.connection_manager.fetchrow_query(
            query, [collection_id]
        )
        return result is not None

    async def get_user_validation_data(
        self,
        user_id: UUID,
    ) -> dict:
        """
        Get verification data for a specific user.
        This method should be called after superuser authorization has been verified.
        """
        query = f"""
            SELECT
                verification_code,
                verification_code_expiry,
                reset_token,
                reset_token_expiry
            FROM {self._get_table_name("users")}
            WHERE id = $1
        """
        result = await self.connection_manager.fetchrow_query(query, [user_id])

        if not result:
            raise R2RException(status_code=404, message="User not found")

        return {
            "verification_data": {
                "verification_code": result["verification_code"],
                "verification_code_expiry": (
                    result["verification_code_expiry"].isoformat()
                    if result["verification_code_expiry"]
                    else None
                ),
                "reset_token": result["reset_token"],
                "reset_token_expiry": (
                    result["reset_token_expiry"].isoformat()
                    if result["reset_token_expiry"]
                    else None
                ),
            }
        }
