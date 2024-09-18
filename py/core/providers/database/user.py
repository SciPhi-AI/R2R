from datetime import datetime
from typing import Optional
from uuid import UUID

from core.base.abstractions import R2RException, UserStats
from core.base.api.models.auth.responses import UserResponse
from core.base.utils import generate_id_from_label

from .base import DatabaseMixin, QueryBuilder


class UserMixin(DatabaseMixin):
    async def create_table(self):
        query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name('users')} (
            user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
        await self.execute_query(query)

    async def get_user_by_id(self, user_id: UUID) -> Optional[UserResponse]:
        query, _ = (
            QueryBuilder(self._get_table_name("users"))
            .select(
                [
                    "user_id",
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
            .where("user_id = $1")
            .build()
        )
        result = await self.fetchrow_query(query, [user_id])

        if not result:
            return None

        return UserResponse(
            id=result["user_id"],
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

    async def get_user_by_email(self, email: str) -> UserResponse:
        query, params = (
            QueryBuilder(self._get_table_name("users"))
            .select(
                [
                    "user_id",
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
        result = await self.fetchrow_query(query, [email])
        if not result:
            raise R2RException(status_code=404, message="User not found")

        return (
            UserResponse(
                id=result["user_id"],
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
            if result
            else None
        )

    async def create_user(self, email: str, password: str) -> UserResponse:
        try:
            if await self.get_user_by_email(email):
                raise R2RException(
                    status_code=400,
                    message="User with this email already exists",
                )
        except R2RException as e:
            if e.status_code != 404:
                raise e

        hashed_password = self.crypto_provider.get_password_hash(password)
        query = f"""
            INSERT INTO {self._get_table_name('users')}
            (email, user_id, hashed_password, collection_ids)
            VALUES ($1, $2, $3, $4)
            RETURNING user_id, email, is_superuser, is_active, is_verified, created_at, updated_at, collection_ids
        """
        result = await self.fetchrow_query(
            query, [email, generate_id_from_label(email), hashed_password, []]
        )

        if not result:
            raise R2RException(
                status_code=500, message="Failed to create user"
            )

        return UserResponse(
            id=result["user_id"],
            email=result["email"],
            is_superuser=result["is_superuser"],
            is_active=result["is_active"],
            is_verified=result["is_verified"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            collection_ids=result["collection_ids"],
            hashed_password=hashed_password,
        )

    async def update_user(self, user: UserResponse) -> UserResponse:
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET email = $1, is_superuser = $2, is_active = $3, is_verified = $4, updated_at = NOW(),
                name = $5, profile_picture = $6, bio = $7, collection_ids = $8
            WHERE user_id = $9
            RETURNING user_id, email, is_superuser, is_active, is_verified, created_at, updated_at, name, profile_picture, bio, collection_ids
        """
        result = await self.fetchrow_query(
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
            raise R2RException(
                status_code=500, message="Failed to update user"
            )

        return UserResponse(
            id=result["user_id"],
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

    async def delete_user(self, user_id: UUID) -> None:
        # Get the collections the user belongs to
        collection_query = f"""
            SELECT collection_ids FROM {self._get_table_name('users')}
            WHERE user_id = $1
        """
        collection_result = await self.fetchrow_query(
            collection_query, [user_id]
        )

        if not collection_result:
            raise R2RException(status_code=404, message="User not found")

        # Remove user from documents
        doc_update_query = f"""
            UPDATE {self._get_table_name('document_info')}
            SET user_id = NULL
            WHERE user_id = $1
        """
        await self.execute_query(doc_update_query, [user_id])

        # Delete the user
        delete_query = f"""
            DELETE FROM {self._get_table_name('users')}
            WHERE user_id = $1
            RETURNING user_id
        """
        result = await self.fetchrow_query(delete_query, [user_id])

        if not result:
            raise R2RException(status_code=404, message="User not found")

    async def update_user_password(
        self, user_id: UUID, new_hashed_password: str
    ):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET hashed_password = $1, updated_at = NOW()
            WHERE user_id = $2
        """
        await self.execute_query(query, [new_hashed_password, user_id])

    async def get_all_users(self) -> list[UserResponse]:
        query = f"""
            SELECT user_id, email, is_superuser, is_active, is_verified, created_at, updated_at, collection_ids
            FROM {self._get_table_name('users')}
        """
        results = await self.fetch_query(query)

        return [
            UserResponse(
                id=result["user_id"],
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
        self, user_id: UUID, verification_code: str, expiry: datetime
    ):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET verification_code = $1, verification_code_expiry = $2
            WHERE user_id = $3
        """
        await self.execute_query(query, [verification_code, expiry, user_id])

    async def verify_user(self, verification_code: str) -> None:
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET is_verified = TRUE, verification_code = NULL, verification_code_expiry = NULL
            WHERE verification_code = $1 AND verification_code_expiry > NOW()
            RETURNING user_id
        """
        result = await self.fetchrow_query(query, [verification_code])

        if not result:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

    async def remove_verification_code(self, verification_code: str):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET verification_code = NULL, verification_code_expiry = NULL
            WHERE verification_code = $1
        """
        await self.execute_query(query, [verification_code])

    async def expire_verification_code(self, user_id: UUID):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET verification_code_expiry = NOW() - INTERVAL '1 day'
            WHERE user_id = $1
        """
        await self.execute_query(query, [user_id])

    async def store_reset_token(
        self, user_id: UUID, reset_token: str, expiry: datetime
    ):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET reset_token = $1, reset_token_expiry = $2
            WHERE user_id = $3
        """
        await self.execute_query(query, [reset_token, expiry, user_id])

    async def get_user_id_by_reset_token(
        self, reset_token: str
    ) -> Optional[UUID]:
        query = f"""
            SELECT user_id FROM {self._get_table_name('users')}
            WHERE reset_token = $1 AND reset_token_expiry > NOW()
        """
        result = await self.fetchrow_query(query, [reset_token])
        return result["user_id"] if result else None

    async def remove_reset_token(self, user_id: UUID):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET reset_token = NULL, reset_token_expiry = NULL
            WHERE user_id = $1
        """
        await self.execute_query(query, [user_id])

    async def remove_user_from_all_collections(self, user_id: UUID):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET collection_ids = ARRAY[]::UUID[]
            WHERE user_id = $1
        """
        await self.execute_query(query, [user_id])

    async def add_user_to_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> None:
        if not await self.get_user_by_id(user_id):
            raise R2RException(status_code=404, message="User not found")

        query = f"""
            UPDATE {self._get_table_name('users')}
            SET collection_ids = array_append(collection_ids, $1)
            WHERE user_id = $2 AND NOT ($1 = ANY(collection_ids))
            RETURNING user_id
        """
        result = await self.fetchrow_query(
            query, [collection_id, user_id]
        )  # fetchrow instead of execute_query
        if not result:
            raise R2RException(
                status_code=400, message="User already in collection"
            )
        return None

    async def remove_user_from_collection(
        self, user_id: UUID, collection_id: UUID
    ) -> None:
        if not await self.get_user_by_id(user_id):
            raise R2RException(status_code=404, message="User not found")

        query = f"""
            UPDATE {self._get_table_name('users')}
            SET collection_ids = array_remove(collection_ids, $1)
            WHERE user_id = $2 AND $1 = ANY(collection_ids)
            RETURNING user_id
        """
        result = await self.fetchrow_query(query, [collection_id, user_id])
        if not result:
            raise R2RException(
                status_code=400,
                message="User is not a member of the specified collection",
            )
        return None

    async def mark_user_as_superuser(self, user_id: UUID):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET is_superuser = TRUE, is_verified = TRUE, verification_code = NULL, verification_code_expiry = NULL
            WHERE user_id = $1
        """
        await self.execute_query(query, [user_id])

    async def get_users_in_collection(
        self, collection_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[UserResponse]:
        query = f"""
            SELECT user_id, email, is_superuser, is_active, is_verified, created_at, updated_at, name, profile_picture, bio, collection_ids
            FROM {self._get_table_name('users')}
            WHERE $1 = ANY(collection_ids)
            ORDER BY email
            OFFSET $2 LIMIT $3
        """
        results = await self.fetch_query(query, [collection_id, offset, limit])

        return [
            UserResponse(
                id=row["user_id"],
                email=row["email"],
                is_superuser=row["is_superuser"],
                is_active=row["is_active"],
                is_verified=row["is_verified"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                name=row["name"],
                profile_picture=row["profile_picture"],
                bio=row["bio"],
                collection_ids=row["collection_ids"],
            )
            for row in results
        ]

    async def get_user_id_by_verification_code(
        self, verification_code: str
    ) -> Optional[UUID]:
        query = f"""
            SELECT user_id FROM {self._get_table_name('users')}
            WHERE verification_code = $1 AND verification_code_expiry > NOW()
        """
        result = await self.fetchrow_query(query, [verification_code])

        if not result:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

        return result["user_id"]

    async def mark_user_as_verified(self, user_id: UUID):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET is_verified = TRUE, verification_code = NULL, verification_code_expiry = NULL
            WHERE user_id = $1
        """
        await self.execute_query(query, [user_id])

    async def get_users_overview(
        self,
        user_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[UserStats]:
        query = f"""
            WITH user_docs AS (
                SELECT
                    u.user_id,
                    u.email,
                    u.is_superuser,
                    u.is_active,
                    u.is_verified,
                    u.created_at,
                    u.updated_at,
                    u.collection_ids,
                    COUNT(d.document_id) AS num_files,
                    COALESCE(SUM(d.size_in_bytes), 0) AS total_size_in_bytes,
                    ARRAY_AGG(d.document_id) FILTER (WHERE d.document_id IS NOT NULL) AS document_ids
                FROM {self._get_table_name('users')} u
                LEFT JOIN {self._get_table_name('document_info')} d ON u.user_id = d.user_id
                {' WHERE u.user_id = ANY($3::uuid[])' if user_ids else ''}
                GROUP BY u.user_id, u.email, u.is_superuser, u.is_active, u.is_verified, u.created_at, u.updated_at, u.collection_ids
            )
            SELECT *
            FROM user_docs
            ORDER BY email
            OFFSET $1
            LIMIT $2
        """

        params = [offset, limit]
        if user_ids:
            params.append(user_ids)

        results = await self.fetch_query(query, params)

        return [
            UserStats(
                user_id=row[0],
                email=row[1],
                is_superuser=row[2],
                is_active=row[3],
                is_verified=row[4],
                created_at=row[5],
                updated_at=row[6],
                collection_ids=row[7] or [],
                num_files=row[8],
                total_size_in_bytes=row[9],
                document_ids=row[10] or [],
            )
            for row in results
        ]
