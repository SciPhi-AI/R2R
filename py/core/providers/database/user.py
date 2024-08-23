from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import text

from core.base.abstractions import R2RException, UserStats
from core.base.api.models.auth.responses import UserResponse
from core.base.utils import generate_id_from_label

from .base import DatabaseMixin, QueryBuilder


class UserMixin(DatabaseMixin):
    def create_table(self):
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
            group_ids UUID[] NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        self.execute_query(query)

    def get_user_by_id(self, user_id: UUID) -> Optional[UserResponse]:
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
                    "group_ids",
                ]
            )
            .where("user_id = :user_id", user_id=user_id)
            .build()
        )
        result = self.execute_query(query, params).fetchone()
        return (
            UserResponse(
                id=result[0],
                email=result[1],
                hashed_password=result[2],
                is_superuser=result[3],
                is_active=result[4],
                is_verified=result[5],
                created_at=result[6],
                updated_at=result[7],
                name=result[8],
                profile_picture=result[9],
                bio=result[10],
                group_ids=result[11],
            )
            if result
            else None
        )

    def get_user_by_email(self, email: str) -> UserResponse:
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
                    "group_ids",
                ]
            )
            .where("email = :email", email=email)
            .build()
        )
        result = self.execute_query(query, params).fetchone()
        if not result:
            raise R2RException(status_code=404, message="User not found")

        return UserResponse(
            id=result[0],
            email=result[1],
            hashed_password=result[2],
            is_superuser=result[3],
            is_active=result[4],
            is_verified=result[5],
            created_at=result[6],
            updated_at=result[7],
            name=result[8],
            profile_picture=result[9],
            bio=result[10],
            group_ids=result[11],
        )

    def create_user(self, email: str, password: str) -> UserResponse:
        try:
            if self.get_user_by_email(email):
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
            (email, user_id, hashed_password, group_ids)
            VALUES (:email, :user_id, :hashed_password, :group_ids)
            RETURNING user_id, email, is_superuser, is_active, is_verified, created_at, updated_at, group_ids
        """
        params = {
            "email": email,
            "user_id": generate_id_from_label(email),
            "hashed_password": hashed_password,
            "group_ids": [],
        }
        result = self.execute_query(query, params).fetchone()
        if not result:
            raise R2RException(
                status_code=500, message="Failed to create user"
            )

        return UserResponse(
            id=result[0],
            email=result[1],
            is_superuser=result[2],
            is_active=result[3],
            is_verified=result[4],
            created_at=result[5],
            updated_at=result[6],
            group_ids=result[7],
            hashed_password=hashed_password,
        )

    def update_user(self, user: UserResponse) -> UserResponse:
        if not self.get_user_by_id(user.id):
            raise R2RException(status_code=404, message="User not found")

        query = f"""
            UPDATE {self._get_table_name('users')}
            SET email = :email, is_superuser = :is_superuser, is_active = :is_active,
                is_verified = :is_verified, updated_at = NOW(), name = :name,
                profile_picture = :profile_picture, bio = :bio, group_ids = :group_ids
            WHERE user_id = :id
            RETURNING user_id, email, is_superuser, is_active, is_verified, created_at,
                      updated_at, name, profile_picture, bio, group_ids
        """
        result = self.execute_query(
            query, user.dict(exclude={"hashed_password"})
        ).fetchone()
        if not result:
            raise R2RException(
                status_code=500, message="Failed to update user"
            )
        return UserResponse(
            id=result[0],
            email=result[1],
            is_superuser=result[2],
            is_active=result[3],
            is_verified=result[4],
            created_at=result[5],
            updated_at=result[6],
            name=result[7],
            profile_picture=result[8],
            bio=result[9],
            group_ids=result[10],
        )

    def delete_user(self, user_id: UUID) -> None:
        # Get the groups the user belongs to
        group_query = f"""
            SELECT group_ids FROM {self._get_table_name('users')}
            WHERE user_id = :user_id
        """
        group_result = self.execute_query(
            group_query, {"user_id": user_id}
        ).fetchone()

        if not group_result:
            raise R2RException(status_code=404, message="User not found")

        user_groups = group_result[0]

        # Remove user from documents
        doc_update_query = f"""
            UPDATE {self._get_table_name('document_info')}
            SET user_id = NULL
            WHERE user_id = :user_id
        """
        self.execute_query(doc_update_query, {"user_id": user_id})

        # Delete the user
        delete_query = f"""
            DELETE FROM {self._get_table_name('users')}
            WHERE user_id = :user_id
            RETURNING user_id
        """

        result = self.execute_query(
            delete_query, {"user_id": user_id}
        ).fetchone()

        if not result:
            raise R2RException(status_code=404, message="User not found")

    def update_user_password(self, user_id: UUID, new_hashed_password: str):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET hashed_password = :new_hashed_password, updated_at = NOW()
            WHERE user_id = :user_id
        """
        self.execute_query(
            query,
            {"user_id": user_id, "new_hashed_password": new_hashed_password},
        )

    def get_all_users(self) -> list[UserResponse]:
        query = f"""
            SELECT user_id, email, is_superuser, is_active, is_verified, created_at, updated_at, group_ids
            FROM {self._get_table_name('users')}
        """
        results = self.execute_query(query).fetchall()
        return [
            UserResponse(
                id=row[0],
                email=row[1],
                hashed_password="null",
                is_superuser=row[2],
                is_active=row[3],
                is_verified=row[4],
                created_at=row[5],
                updated_at=row[6],
                group_ids=row[7],
            )
            for row in results
        ]

    def store_verification_code(
        self, user_id: UUID, verification_code: str, expiry: datetime
    ):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET verification_code = :code, verification_code_expiry = :expiry
            WHERE user_id = :user_id
        """
        self.execute_query(
            query,
            {"code": verification_code, "expiry": expiry, "user_id": user_id},
        )

    def verify_user(self, verification_code: str) -> None:
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET is_verified = TRUE, verification_code = NULL, verification_code_expiry = NULL
            WHERE verification_code = :code AND verification_code_expiry > NOW()
            RETURNING user_id
        """
        result = self.execute_query(
            query, {"code": verification_code}
        ).fetchone()
        if not result:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )
        return None

    def remove_verification_code(self, verification_code: str):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET verification_code = NULL, verification_code_expiry = NULL
            WHERE verification_code = :code
        """
        self.execute_query(query, {"code": verification_code})

    def expire_verification_code(self, user_id: UUID):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET verification_code_expiry = NOW() - INTERVAL '1 day'
            WHERE user_id = :user_id
        """
        self.execute_query(query, {"user_id": user_id})

    def store_reset_token(
        self, user_id: UUID, reset_token: str, expiry: datetime
    ):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET reset_token = :token, reset_token_expiry = :expiry
            WHERE user_id = :user_id
        """
        self.execute_query(
            query, {"token": reset_token, "expiry": expiry, "user_id": user_id}
        )

    def get_user_id_by_reset_token(self, reset_token: str) -> Optional[UUID]:
        query = f"""
            SELECT user_id FROM {self._get_table_name('users')}
            WHERE reset_token = :token AND reset_token_expiry > NOW()
        """
        result = self.execute_query(query, {"token": reset_token}).fetchone()
        return result[0] if result else None

    def remove_reset_token(self, user_id: UUID):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET reset_token = NULL, reset_token_expiry = NULL
            WHERE user_id = :user_id
        """
        self.execute_query(query, {"user_id": user_id})

    def remove_user_from_all_groups(self, user_id: UUID):
        query = f"""
            UPDATE {self._get_table_name('users')}
            SET group_ids = ARRAY[]::UUID[]
            WHERE user_id = :user_id
        """
        self.execute_query(query, {"user_id": user_id})

    def add_user_to_group(self, user_id: UUID, group_id: UUID) -> None:
        if not self.get_user_by_id(user_id):
            raise R2RException(status_code=404, message="User not found")

        query = f"""
            UPDATE {self._get_table_name('users')}
            SET group_ids = array_append(group_ids, :group_id)
            WHERE user_id = :user_id AND NOT (:group_id = ANY(group_ids))
            RETURNING user_id
        """
        result = self.execute_query(
            query, {"user_id": user_id, "group_id": group_id}
        ).fetchone()
        if not result:
            raise R2RException(
                status_code=400, message="User already in group"
            )
        return None

    def remove_user_from_group(self, user_id: UUID, group_id: UUID) -> None:
        if not self.get_user_by_id(user_id):
            raise R2RException(status_code=404, message="User not found")

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
                status_code=400,
                message="User is not a member of the specified group",
            )
        return None

    def mark_user_as_superuser(self, user_id: UUID):
        query = text(
            f"""
        UPDATE users_{self.collection_name}
        SET is_superuser = TRUE, is_verified = TRUE, verification_code = NULL, verification_code_expiry = NULL
        WHERE user_id = :user_id
        """
        )

        with self.vx.Session() as sess:
            sess.execute(query, {"user_id": user_id})
            sess.commit()

    def get_users_in_group(
        self, group_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[UserResponse]:
        query = f"""
            SELECT user_id, email, is_superuser, is_active, is_verified, created_at, updated_at, name, profile_picture, bio, group_ids
            FROM {self._get_table_name('users')}
            WHERE :group_id = ANY(group_ids)
            ORDER BY email
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
                is_superuser=row[2],
                is_active=row[3],
                is_verified=row[4],
                created_at=row[5],
                updated_at=row[6],
                name=row[7],
                profile_picture=row[8],
                bio=row[9],
                group_ids=row[10],
            )
            for row in results
        ]

    def get_user_id_by_verification_code(
        self, verification_code: str
    ) -> Optional[UUID]:
        query = text(
            f"""
        SELECT user_id FROM users_{self.collection_name}
        WHERE verification_code = :code AND verification_code_expiry > NOW()
        """
        )

        with self.vx.Session() as sess:
            result = sess.execute(query, {"code": verification_code})
            user_data = result.fetchone()

        if not user_data:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )
        return user_data[0]

    def mark_user_as_verified(self, user_id: UUID):
        query = text(
            f"""
        UPDATE users_{self.collection_name}
        SET is_verified = TRUE, verification_code = NULL, verification_code_expiry = NULL
        WHERE user_id = :user_id
        """
        )

        with self.vx.Session() as sess:
            result = sess.execute(query, {"user_id": user_id})
            sess.commit()

        if not result.rowcount:
            raise R2RException(status_code=404, message="User not found")

    def get_users_overview(
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
                    u.group_ids,
                    COUNT(d.document_id) AS num_files,
                    COALESCE(SUM(d.size_in_bytes), 0) AS total_size_in_bytes,
                    ARRAY_AGG(d.document_id) FILTER (WHERE d.document_id IS NOT NULL) AS document_ids
                FROM {self._get_table_name('users')} u
                LEFT JOIN {self._get_table_name('document_info')} d ON u.user_id = d.user_id
                {f"WHERE u.user_id = ANY(CAST(:user_ids AS UUID[]))" if user_ids else ""}
                GROUP BY u.user_id, u.email, u.is_superuser, u.is_active, u.is_verified, u.created_at, u.updated_at, u.group_ids
            )
            SELECT *
            FROM user_docs
            ORDER BY email
            OFFSET :offset
            LIMIT :limit
        """

        params = {"offset": offset, "limit": limit}
        if user_ids:
            params["user_ids"] = [str(ele) for ele in user_ids]

        results = self.execute_query(query, params).fetchall()

        return [
            UserStats(
                user_id=row[0],
                email=row[1],
                is_superuser=row[2],
                is_active=row[3],
                is_verified=row[4],
                created_at=row[5],
                updated_at=row[6],
                group_ids=row[7] or [],
                num_files=row[8],
                total_size_in_bytes=row[9],
                document_ids=row[10] or [],
            )
            for row in results
        ]
