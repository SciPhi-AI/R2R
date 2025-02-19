import csv
import json
import tempfile
from datetime import datetime
from typing import IO, Optional
from uuid import UUID

from fastapi import HTTPException

from core.base import CryptoProvider, Handler
from core.base.abstractions import R2RException
from core.utils import generate_user_id
from shared.abstractions import User

from .base import PostgresConnectionManager, QueryBuilder
from .collections import PostgresCollectionsHandler


def _merge_metadata(
    existing_metadata: dict[str, str], new_metadata: dict[str, Optional[str]]
) -> dict[str, str]:
    """
    Merges the new metadata with the existing metadata in the Stripe-style approach:
      - new_metadata[key] = <string> => update or add that key
      - new_metadata[key] = ""       => remove that key
      - if new_metadata is empty => remove all keys
    """
    # If new_metadata is an empty dict, it signals removal of all keys.
    if new_metadata == {}:
        return {}

    # Copy so we don't mutate the original
    final_metadata = dict(existing_metadata)

    for key, value in new_metadata.items():
        # If the user sets the key to an empty string, it means "delete" that key
        if value == "":
            if key in final_metadata:
                del final_metadata[key]
        # If not None and not empty, set or override
        elif value is not None:
            final_metadata[key] = value
        else:
            # If the user sets the value to None in some contexts, decide if you want to remove or ignore
            # For now we might treat None same as empty string => remove
            if key in final_metadata:
                del final_metadata[key]

    return final_metadata


class PostgresUserHandler(Handler):
    TABLE_NAME = "users"
    API_KEYS_TABLE_NAME = "users_api_keys"

    def __init__(
        self,
        project_name: str,
        connection_manager: PostgresConnectionManager,
        crypto_provider: CryptoProvider,
    ):
        super().__init__(project_name, connection_manager)
        self.crypto_provider = crypto_provider

    async def create_tables(self):
        user_table_query = f"""
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
            limits_overrides JSONB,
            metadata JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            account_type TEXT NOT NULL DEFAULT 'password',
            google_id TEXT,
            github_id TEXT
        );
        """

        # API keys table with updated_at instead of last_used_at
        api_keys_table_query = f"""
        CREATE TABLE IF NOT EXISTS {self._get_table_name(PostgresUserHandler.API_KEYS_TABLE_NAME)} (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES {self._get_table_name(PostgresUserHandler.TABLE_NAME)}(id) ON DELETE CASCADE,
            public_key TEXT UNIQUE NOT NULL,
            hashed_key TEXT NOT NULL,
            name TEXT,
            description TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_api_keys_user_id
        ON {self._get_table_name(PostgresUserHandler.API_KEYS_TABLE_NAME)}(user_id);

        CREATE INDEX IF NOT EXISTS idx_api_keys_public_key
        ON {self._get_table_name(PostgresUserHandler.API_KEYS_TABLE_NAME)}(public_key);
        """

        await self.connection_manager.execute_query(user_table_query)
        await self.connection_manager.execute_query(api_keys_table_query)

        # (New) Code snippet for adding columns if missing
        # Postgres >= 9.6 supports "ADD COLUMN IF NOT EXISTS"
        check_columns_query = f"""
        ALTER TABLE {self._get_table_name(self.TABLE_NAME)}
            ADD COLUMN IF NOT EXISTS metadata JSONB;

        ALTER TABLE {self._get_table_name(self.TABLE_NAME)}
            ADD COLUMN IF NOT EXISTS limits_overrides JSONB;

        ALTER TABLE {self._get_table_name(self.API_KEYS_TABLE_NAME)}
            ADD COLUMN IF NOT EXISTS description TEXT;
        """
        await self.connection_manager.execute_query(check_columns_query)

        # Optionally, create indexes for quick lookups:
        check_columns_query = f"""
        ALTER TABLE {self._get_table_name(self.TABLE_NAME)}
            ADD COLUMN IF NOT EXISTS account_type TEXT NOT NULL DEFAULT 'password',
            ADD COLUMN IF NOT EXISTS google_id TEXT,
            ADD COLUMN IF NOT EXISTS github_id TEXT;

        CREATE INDEX IF NOT EXISTS idx_users_google_id
            ON {self._get_table_name(self.TABLE_NAME)}(google_id);
        CREATE INDEX IF NOT EXISTS idx_users_github_id
            ON {self._get_table_name(self.TABLE_NAME)}(github_id);
        """
        await self.connection_manager.execute_query(check_columns_query)

    async def get_user_by_id(self, id: UUID) -> User:
        query, _ = (
            QueryBuilder(self._get_table_name("users"))
            .select(
                [
                    "id",
                    "email",
                    "is_superuser",
                    "is_active",
                    "is_verified",
                    "created_at",
                    "updated_at",
                    "name",
                    "profile_picture",
                    "bio",
                    "collection_ids",
                    "limits_overrides",
                    "metadata",
                    "account_type",
                    "hashed_password",
                    "google_id",
                    "github_id",
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
            is_superuser=result["is_superuser"],
            is_active=result["is_active"],
            is_verified=result["is_verified"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            name=result["name"],
            profile_picture=result["profile_picture"],
            bio=result["bio"],
            collection_ids=result["collection_ids"],
            limits_overrides=json.loads(result["limits_overrides"] or "{}"),
            metadata=json.loads(result["metadata"] or "{}"),
            hashed_password=result["hashed_password"],
            account_type=result["account_type"],
            google_id=result["google_id"],
            github_id=result["github_id"],
        )

    async def get_user_by_email(self, email: str) -> User:
        query, params = (
            QueryBuilder(self._get_table_name("users"))
            .select(
                [
                    "id",
                    "email",
                    "is_superuser",
                    "is_active",
                    "is_verified",
                    "created_at",
                    "updated_at",
                    "name",
                    "profile_picture",
                    "bio",
                    "collection_ids",
                    "metadata",
                    "limits_overrides",
                    "account_type",
                    "hashed_password",
                    "google_id",
                    "github_id",
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
            is_superuser=result["is_superuser"],
            is_active=result["is_active"],
            is_verified=result["is_verified"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            name=result["name"],
            profile_picture=result["profile_picture"],
            bio=result["bio"],
            collection_ids=result["collection_ids"],
            limits_overrides=json.loads(result["limits_overrides"] or "{}"),
            metadata=json.loads(result["metadata"] or "{}"),
            account_type=result["account_type"],
            hashed_password=result["hashed_password"],
            google_id=result["google_id"],
            github_id=result["github_id"],
        )

    async def create_user(
        self,
        email: str,
        password: Optional[str] = None,
        account_type: Optional[str] = "password",
        google_id: Optional[str] = None,
        github_id: Optional[str] = None,
        is_superuser: bool = False,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        # 1) Check if a user with this email already exists
        try:
            existing = await self.get_user_by_email(email)
            if existing:
                raise R2RException(
                    status_code=400,
                    message="User with this email already exists",
                )
        except R2RException as e:
            if e.status_code != 404:
                raise e
        # 2) If google_id is provided, ensure no user already has it
        if google_id:
            existing_google_user = await self.get_user_by_google_id(google_id)
            if existing_google_user:
                raise R2RException(
                    status_code=400,
                    message="User with this Google account already exists",
                )

        # 3) If github_id is provided, ensure no user already has it
        if github_id:
            existing_github_user = await self.get_user_by_github_id(github_id)
            if existing_github_user:
                raise R2RException(
                    status_code=400,
                    message="User with this GitHub account already exists",
                )

        hashed_password = None
        if account_type == "password":
            if password is None:
                raise R2RException(
                    status_code=400,
                    message="Password is required for a 'password' account_type",
                )
            hashed_password = self.crypto_provider.get_password_hash(password)  # type: ignore

        query, params = (
            QueryBuilder(self._get_table_name(self.TABLE_NAME))
            .insert(
                {
                    "email": email,
                    "id": generate_user_id(email),
                    "is_superuser": is_superuser,
                    "collection_ids": [],
                    "limits_overrides": None,
                    "metadata": None,
                    "account_type": account_type,
                    "hashed_password": hashed_password
                    or "",  # Ensure hashed_password is not None
                    # !!WARNING - Upstream checks are required to treat oauth differently from password!!
                    "google_id": google_id,
                    "github_id": github_id,
                    "is_verified": account_type != "password",
                    "name": name,
                    "bio": bio,
                    "profile_picture": profile_picture,
                }
            )
            .returning(
                [
                    "id",
                    "email",
                    "is_superuser",
                    "is_active",
                    "is_verified",
                    "created_at",
                    "updated_at",
                    "collection_ids",
                    "limits_overrides",
                    "metadata",
                    "name",
                    "bio",
                    "profile_picture",
                ]
            )
            .build()
        )

        result = await self.connection_manager.fetchrow_query(query, params)
        if not result:
            raise R2RException(
                status_code=500,
                message="Failed to create user",
            )

        return User(
            id=result["id"],
            email=result["email"],
            is_superuser=result["is_superuser"],
            is_active=result["is_active"],
            is_verified=result["is_verified"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            collection_ids=result["collection_ids"] or [],
            limits_overrides=json.loads(result["limits_overrides"] or "{}"),
            metadata=json.loads(result["metadata"] or "{}"),
            name=result["name"],
            bio=result["bio"],
            profile_picture=result["profile_picture"],
            account_type=account_type or "password",
            hashed_password=hashed_password,
            google_id=google_id,
            github_id=github_id,
        )

    async def update_user(
        self,
        user: User,
        merge_limits: bool = False,
        new_metadata: dict[str, Optional[str]] | None = None,
    ) -> User:
        """Update user information including limits_overrides.

        Args:
            user: User object containing updated information
            merge_limits: If True, will merge existing limits_overrides with new ones.
                        If False, will overwrite existing limits_overrides.

        Returns:
            Updated User object
        """

        # Get current user if we need to merge limits or get hashed password
        current_user = None
        try:
            current_user = await self.get_user_by_id(user.id)
        except R2RException:
            raise R2RException(
                status_code=404, message="User not found"
            ) from None

        # If the new user.google_id != current_user.google_id, check for duplicates
        if user.email and (user.email != current_user.email):
            existing_email_user = await self.get_user_by_email(user.email)
            if existing_email_user and existing_email_user.id != user.id:
                raise R2RException(
                    status_code=400,
                    message="That email account is already associated with another user.",
                )

        # If the new user.google_id != current_user.google_id, check for duplicates
        if user.google_id and (user.google_id != current_user.google_id):
            existing_google_user = await self.get_user_by_google_id(
                user.google_id
            )
            if existing_google_user and existing_google_user.id != user.id:
                raise R2RException(
                    status_code=400,
                    message="That Google account is already associated with another user.",
                )

        # Similarly for GitHub:
        if user.github_id and (user.github_id != current_user.github_id):
            existing_github_user = await self.get_user_by_github_id(
                user.github_id
            )
            if existing_github_user and existing_github_user.id != user.id:
                raise R2RException(
                    status_code=400,
                    message="That GitHub account is already associated with another user.",
                )

        # Merge or replace metadata if provided
        final_metadata = current_user.metadata or {}
        if new_metadata is not None:
            final_metadata = _merge_metadata(final_metadata, new_metadata)

        # Merge or replace limits_overrides
        final_limits = user.limits_overrides
        if (
            merge_limits
            and current_user.limits_overrides
            and user.limits_overrides
        ):
            final_limits = {
                **current_user.limits_overrides,
                **user.limits_overrides,
            }
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET email = $1,
                is_superuser = $2,
                is_active = $3,
                is_verified = $4,
                updated_at = NOW(),
                name = $5,
                profile_picture = $6,
                bio = $7,
                collection_ids = $8,
                limits_overrides = $9::jsonb,
                metadata = $10::jsonb
            WHERE id = $11
            RETURNING id, email, is_superuser, is_active, is_verified,
                    created_at, updated_at, name, profile_picture, bio,
                    collection_ids, limits_overrides, metadata, hashed_password,
                    account_type, google_id, github_id
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
                user.collection_ids or [],
                json.dumps(final_limits),
                json.dumps(final_metadata),
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
            collection_ids=result["collection_ids"]
            or [],  # Ensure null becomes empty array
            limits_overrides=json.loads(
                result["limits_overrides"] or "{}"
            ),  # Can be null
            metadata=json.loads(result["metadata"] or "{}"),
            account_type=result["account_type"],
            hashed_password=result[
                "hashed_password"
            ],  # Include hashed_password
            google_id=result["google_id"],
            github_id=result["github_id"],
        )

    async def delete_user_relational(self, id: UUID) -> None:
        """Delete a user and update related records."""
        # Get the collections the user belongs to
        collection_query, params = (
            QueryBuilder(self._get_table_name(self.TABLE_NAME))
            .select(["collection_ids"])
            .where("id = $1")
            .build()
        )

        collection_result = await self.connection_manager.fetchrow_query(
            collection_query, [id]
        )

        if not collection_result:
            raise R2RException(status_code=404, message="User not found")

        # Update documents query
        doc_update_query, doc_params = (
            QueryBuilder(self._get_table_name("documents"))
            .update({"id": None})
            .where("id = $1")
            .build()
        )

        await self.connection_manager.execute_query(doc_update_query, [id])

        # Delete user query
        delete_query, del_params = (
            QueryBuilder(self._get_table_name(self.TABLE_NAME))
            .delete()
            .where("id = $1")
            .returning(["id"])
            .build()
        )

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
        """Get all users with minimal information."""
        query, params = (
            QueryBuilder(self._get_table_name(self.TABLE_NAME))
            .select(
                [
                    "id",
                    "email",
                    "is_superuser",
                    "is_active",
                    "is_verified",
                    "created_at",
                    "updated_at",
                    "collection_ids",
                    "hashed_password",
                    "limits_overrides",
                    "metadata",
                    "name",
                    "bio",
                    "profile_picture",
                    "account_type",
                    "google_id",
                    "github_id",
                ]
            )
            .build()
        )

        results = await self.connection_manager.fetch_query(query, params)
        return [
            User(
                id=result["id"],
                email=result["email"],
                is_superuser=result["is_superuser"],
                is_active=result["is_active"],
                is_verified=result["is_verified"],
                created_at=result["created_at"],
                updated_at=result["updated_at"],
                collection_ids=result["collection_ids"] or [],
                limits_overrides=json.loads(
                    result["limits_overrides"] or "{}"
                ),
                metadata=json.loads(result["metadata"] or "{}"),
                name=result["name"],
                bio=result["bio"],
                profile_picture=result["profile_picture"],
                account_type=result["account_type"],
                hashed_password=result["hashed_password"],
                google_id=result["google_id"],
                github_id=result["github_id"],
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
        # Check if the user exists
        if not await self.get_user_by_id(id):
            raise R2RException(status_code=404, message="User not found")

        # Check if the collection exists
        if not await self._collection_exists(collection_id):
            raise R2RException(status_code=404, message="Collection not found")

        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET collection_ids = array_append(collection_ids, $1)
            WHERE id = $2 AND NOT ($1 = ANY(collection_ids))
            RETURNING id
        """
        result = await self.connection_manager.fetchrow_query(
            query, [collection_id, id]
        )
        if not result:
            raise R2RException(
                status_code=400, message="User already in collection"
            )

        update_collection_query = f"""
            UPDATE {self._get_table_name("collections")}
            SET user_count = user_count + 1
            WHERE id = $1
        """
        await self.connection_manager.execute_query(
            query=update_collection_query,
            params=[collection_id],
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
        """Get all users in a specific collection with pagination."""
        if not await self._collection_exists(collection_id):
            raise R2RException(status_code=404, message="Collection not found")

        query, params = (
            QueryBuilder(self._get_table_name(self.TABLE_NAME))
            .select(
                [
                    "id",
                    "email",
                    "is_active",
                    "is_superuser",
                    "created_at",
                    "updated_at",
                    "is_verified",
                    "collection_ids",
                    "name",
                    "bio",
                    "profile_picture",
                    "limits_overrides",
                    "metadata",
                    "account_type",
                    "hashed_password",
                    "google_id",
                    "github_id",
                    "COUNT(*) OVER() AS total_entries",
                ]
            )
            .where("$1 = ANY(collection_ids)")
            .order_by("name")
            .offset("$2")
            .limit("$3" if limit != -1 else None)
            .build()
        )

        conditions = [collection_id, offset]
        if limit != -1:
            conditions.append(limit)

        results = await self.connection_manager.fetch_query(query, conditions)

        users_list = [
            User(
                id=row["id"],
                email=row["email"],
                is_active=row["is_active"],
                is_superuser=row["is_superuser"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                is_verified=row["is_verified"],
                collection_ids=row["collection_ids"] or [],
                name=row["name"],
                bio=row["bio"],
                profile_picture=row["profile_picture"],
                limits_overrides=json.loads(row["limits_overrides"] or "{}"),
                metadata=json.loads(row["metadata"] or "{}"),
                account_type=row["account_type"],
                hashed_password=row["hashed_password"],
                google_id=row["google_id"],
                github_id=row["github_id"],
            )
            for row in results
        ]

        total_entries = results[0]["total_entries"] if results else 0
        return {"results": users_list, "total_entries": total_entries}

    async def mark_user_as_superuser(self, id: UUID):
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.TABLE_NAME)}
            SET is_superuser = TRUE, is_verified = TRUE,
                verification_code = NULL, verification_code_expiry = NULL
            WHERE id = $1
        """
        await self.connection_manager.execute_query(query, [id])

    async def get_user_id_by_verification_code(
        self, verification_code: str
    ) -> UUID:
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
            SET is_verified = TRUE,
                verification_code = NULL,
                verification_code_expiry = NULL
            WHERE id = $1
        """
        await self.connection_manager.execute_query(query, [id])

    async def get_users_overview(
        self,
        offset: int,
        limit: int,
        user_ids: Optional[list[UUID]] = None,
    ) -> dict[str, list[User] | int]:
        """Return users with document usage and total entries."""
        query = f"""
            WITH user_document_ids AS (
                SELECT
                    u.id as user_id,
                    ARRAY_AGG(d.id) FILTER (WHERE d.id IS NOT NULL) AS doc_ids
                FROM {self._get_table_name(PostgresUserHandler.TABLE_NAME)} u
                LEFT JOIN {self._get_table_name("documents")} d ON u.id = d.owner_id
                GROUP BY u.id
            ),
            user_docs AS (
                SELECT
                    u.id,
                    u.email,
                    u.is_superuser,
                    u.is_active,
                    u.is_verified,
                    u.name,
                    u.bio,
                    u.profile_picture,
                    u.collection_ids,
                    u.created_at,
                    u.updated_at,
                    COUNT(d.id) AS num_files,
                    COALESCE(SUM(d.size_in_bytes), 0) AS total_size_in_bytes,
                    ud.doc_ids as document_ids
                FROM {self._get_table_name(PostgresUserHandler.TABLE_NAME)} u
                LEFT JOIN {self._get_table_name("documents")} d ON u.id = d.owner_id
                LEFT JOIN user_document_ids ud ON u.id = ud.user_id
                {" WHERE u.id = ANY($3::uuid[])" if user_ids else ""}
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
        if not results:
            raise R2RException(status_code=404, message="No users found")

        users_list = []
        for row in results:
            users_list.append(
                User(
                    id=row["id"],
                    email=row["email"],
                    is_superuser=row["is_superuser"],
                    is_active=row["is_active"],
                    is_verified=row["is_verified"],
                    name=row["name"],
                    bio=row["bio"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    profile_picture=row["profile_picture"],
                    collection_ids=row["collection_ids"] or [],
                    num_files=row["num_files"],
                    total_size_in_bytes=row["total_size_in_bytes"],
                    document_ids=(
                        list(row["document_ids"])
                        if row["document_ids"]
                        else []
                    ),
                )
            )

        total_entries = results[0]["total_entries"]
        return {"results": users_list, "total_entries": total_entries}

    async def _collection_exists(self, collection_id: UUID) -> bool:
        """Check if a collection exists."""
        query = f"""
            SELECT 1 FROM {self._get_table_name(PostgresCollectionsHandler.TABLE_NAME)}
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
        """Get verification data for a specific user.

        This method should be called after superuser authorization has been
        verified.
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

    # API Key methods
    async def store_user_api_key(
        self,
        user_id: UUID,
        key_id: str,
        hashed_key: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> UUID:
        """Store a new API key for a user with optional name and
        description."""
        query = f"""
            INSERT INTO {self._get_table_name(PostgresUserHandler.API_KEYS_TABLE_NAME)}
            (user_id, public_key, hashed_key, name, description)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """
        result = await self.connection_manager.fetchrow_query(
            query, [user_id, key_id, hashed_key, name or "", description or ""]
        )
        if not result:
            raise R2RException(
                status_code=500, message="Failed to store API key"
            )
        return result["id"]

    async def get_api_key_record(self, key_id: str) -> Optional[dict]:
        """Get API key record by 'public_key' and update 'updated_at' to now.

        Returns { "user_id", "hashed_key" } or None if not found.
        """
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.API_KEYS_TABLE_NAME)}
            SET updated_at = NOW()
            WHERE public_key = $1
            RETURNING user_id, hashed_key
        """
        result = await self.connection_manager.fetchrow_query(query, [key_id])
        if not result:
            return None
        return {
            "user_id": result["user_id"],
            "hashed_key": result["hashed_key"],
        }

    async def get_user_api_keys(self, user_id: UUID) -> list[dict]:
        """Get all API keys for a user."""
        query = f"""
            SELECT id, public_key, name, description, created_at, updated_at
            FROM {self._get_table_name(PostgresUserHandler.API_KEYS_TABLE_NAME)}
            WHERE user_id = $1
            ORDER BY created_at DESC
        """
        results = await self.connection_manager.fetch_query(query, [user_id])
        return [
            {
                "key_id": str(row["id"]),
                "public_key": row["public_key"],
                "name": row["name"] or "",
                "description": row["description"] or "",
                "updated_at": row["updated_at"],
            }
            for row in results
        ]

    async def delete_api_key(self, user_id: UUID, key_id: UUID) -> bool:
        """Delete a specific API key."""
        query = f"""
            DELETE FROM {self._get_table_name(PostgresUserHandler.API_KEYS_TABLE_NAME)}
            WHERE id = $1 AND user_id = $2
            RETURNING id, public_key, name, description
        """
        result = await self.connection_manager.fetchrow_query(
            query, [key_id, user_id]
        )
        if result is None:
            raise R2RException(status_code=404, message="API key not found")

        return True

    async def update_api_key_name(
        self, user_id: UUID, key_id: UUID, name: str
    ) -> bool:
        """Update the name of an existing API key."""
        query = f"""
            UPDATE {self._get_table_name(PostgresUserHandler.API_KEYS_TABLE_NAME)}
            SET name = $1, updated_at = NOW()
            WHERE id = $2 AND user_id = $3
            RETURNING id
        """
        result = await self.connection_manager.fetchrow_query(
            query, [name, key_id, user_id]
        )
        if result is None:
            raise R2RException(status_code=404, message="API key not found")
        return True

    async def export_to_csv(
        self,
        columns: Optional[list[str]] = None,
        filters: Optional[dict] = None,
        include_header: bool = True,
    ) -> tuple[str, IO]:
        """Creates a CSV file from the PostgreSQL data and returns the path to
        the temp file."""
        valid_columns = {
            "id",
            "email",
            "is_superuser",
            "is_active",
            "is_verified",
            "name",
            "bio",
            "collection_ids",
            "created_at",
            "updated_at",
        }

        if not columns:
            columns = list(valid_columns)
        elif invalid_cols := set(columns) - valid_columns:
            raise ValueError(f"Invalid columns: {invalid_cols}")

        select_stmt = f"""
            SELECT
                id::text,
                email,
                is_superuser,
                is_active,
                is_verified,
                name,
                bio,
                collection_ids::text,
                to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                to_char(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM {self._get_table_name(self.TABLE_NAME)}
        """

        params = []
        if filters:
            conditions = []
            param_index = 1

            for field, value in filters.items():
                if field not in valid_columns:
                    continue

                if isinstance(value, dict):
                    for op, val in value.items():
                        if op == "$eq":
                            conditions.append(f"{field} = ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$gt":
                            conditions.append(f"{field} > ${param_index}")
                            params.append(val)
                            param_index += 1
                        elif op == "$lt":
                            conditions.append(f"{field} < ${param_index}")
                            params.append(val)
                            param_index += 1
                else:
                    # Direct equality
                    conditions.append(f"{field} = ${param_index}")
                    params.append(value)
                    param_index += 1

            if conditions:
                select_stmt = f"{select_stmt} WHERE {' AND '.join(conditions)}"

        select_stmt = f"{select_stmt} ORDER BY created_at DESC"

        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", delete=True, suffix=".csv"
            )
            writer = csv.writer(temp_file, quoting=csv.QUOTE_ALL)

            async with self.connection_manager.pool.get_connection() as conn:  # type: ignore
                async with conn.transaction():
                    cursor = await conn.cursor(select_stmt, *params)

                    if include_header:
                        writer.writerow(columns)

                    chunk_size = 1000
                    while True:
                        rows = await cursor.fetch(chunk_size)
                        if not rows:
                            break
                        for row in rows:
                            row_dict = {
                                "id": row[0],
                                "email": row[1],
                                "is_superuser": row[2],
                                "is_active": row[3],
                                "is_verified": row[4],
                                "name": row[5],
                                "bio": row[6],
                                "collection_ids": row[7],
                                "created_at": row[8],
                                "updated_at": row[9],
                            }
                            writer.writerow([row_dict[col] for col in columns])

            temp_file.flush()
            return temp_file.name, temp_file

        except Exception as e:
            if temp_file:
                temp_file.close()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to export data: {str(e)}",
            ) from e

    async def get_user_by_google_id(self, google_id: str) -> Optional[User]:
        """Return a User if the google_id is found; otherwise None."""
        query, params = (
            QueryBuilder(self._get_table_name("users"))
            .select(
                [
                    "id",
                    "email",
                    "is_superuser",
                    "is_active",
                    "is_verified",
                    "created_at",
                    "updated_at",
                    "name",
                    "profile_picture",
                    "bio",
                    "collection_ids",
                    "limits_overrides",
                    "metadata",
                    "account_type",
                    "hashed_password",
                    "google_id",
                    "github_id",
                ]
            )
            .where("google_id = $1")
            .build()
        )
        result = await self.connection_manager.fetchrow_query(
            query, [google_id]
        )
        if not result:
            return None

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
            collection_ids=result["collection_ids"] or [],
            limits_overrides=json.loads(result["limits_overrides"] or "{}"),
            metadata=json.loads(result["metadata"] or "{}"),
            account_type=result["account_type"],
            hashed_password=result["hashed_password"],
            google_id=result["google_id"],
            github_id=result["github_id"],
        )

    async def get_user_by_github_id(self, github_id: str) -> Optional[User]:
        """Return a User if the github_id is found; otherwise None."""
        query, params = (
            QueryBuilder(self._get_table_name("users"))
            .select(
                [
                    "id",
                    "email",
                    "is_superuser",
                    "is_active",
                    "is_verified",
                    "created_at",
                    "updated_at",
                    "name",
                    "profile_picture",
                    "bio",
                    "collection_ids",
                    "limits_overrides",
                    "metadata",
                    "account_type",
                    "hashed_password",
                    "google_id",
                    "github_id",
                ]
            )
            .where("github_id = $1")
            .build()
        )
        result = await self.connection_manager.fetchrow_query(
            query, [github_id]
        )
        if not result:
            return None

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
            collection_ids=result["collection_ids"] or [],
            limits_overrides=json.loads(result["limits_overrides"] or "{}"),
            metadata=json.loads(result["metadata"] or "{}"),
            account_type=result["account_type"],
            hashed_password=result["hashed_password"],
            google_id=result["google_id"],
            github_id=result["github_id"],
        )
