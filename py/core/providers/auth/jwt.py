import logging
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends

from core.base import (
    AuthConfig,
    AuthProvider,
    CryptoProvider,
    EmailProvider,
    R2RException,
    Token,
    TokenData,
)
from core.base.api.models import User

from ..database import PostgresDatabaseProvider

logger = logging.getLogger()


class JwtAuthProvider(AuthProvider):
    def __init__(
        self,
        config: AuthConfig,
        crypto_provider: CryptoProvider,
        database_provider: PostgresDatabaseProvider,
        email_provider: EmailProvider,
    ):
        super().__init__(
            config, crypto_provider, database_provider, email_provider
        )

    async def login(self, email: str, password: str) -> dict[str, Token]:
        raise NotImplementedError("Not implemented")

    async def oauth_callback(self, code: str) -> dict[str, Token]:
        raise NotImplementedError("Not implemented")

    async def user(self, token: str) -> User:
        raise NotImplementedError("Not implemented")

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> dict[str, str]:
        raise NotImplementedError("Not implemented")

    async def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict[str, str]:
        raise NotImplementedError("Not implemented")

    def create_access_token(self, data: dict) -> str:
        raise NotImplementedError("Not implemented")

    def create_refresh_token(self, data: dict) -> str:
        raise NotImplementedError("Not implemented")

    async def decode_token(self, token: str) -> TokenData:
        # use JWT library to validate and decode JWT token
        jwtSecret = os.getenv("JWT_SECRET")
        if jwtSecret is None:
            raise R2RException(
                status_code=500,
                message="JWT_SECRET environment variable is not set",
            )
        try:
            user = jwt.decode(token, jwtSecret, algorithms=["HS256"])
        except Exception as e:
            logger.info(f"JWT verification failed: {e}")
            raise R2RException(
                status_code=401, message="Invalid JWT token", detail=e
            ) from e
        if user:
            # Create user in database if not exists
            try:
                await self.database_provider.users_handler.get_user_by_email(
                    user.get("email")
                )
                # TODO do we want to update user info here based on what's in the token?
            except Exception:
                # user doesn't exist, create in db
                logger.debug(f"Creating new user: {user.get('email')}")
                try:
                    await self.database_provider.users_handler.create_user(
                        email=user.get("email"),
                        account_type="external",
                        name=user.get("name"),
                    )
                except Exception as e:
                    logger.error(f"Error creating user: {e}")
                    raise R2RException(
                        status_code=500, message="Failed to create user"
                    ) from e
            return TokenData(
                email=user.get("email"),
                token_type="bearer",
                exp=user.get("exp"),
            )
        else:
            raise R2RException(status_code=401, message="Invalid JWT token")

    async def refresh_access_token(
        self, refresh_token: str
    ) -> dict[str, Token]:
        raise NotImplementedError("Not implemented")

    def get_current_active_user(
        self, current_user: User = Depends(user)
    ) -> User:
        # Check if user is active
        if not current_user.is_active:
            raise R2RException(status_code=400, message="Inactive user")
        return current_user

    async def logout(self, token: str) -> dict[str, str]:
        raise NotImplementedError("Not implemented")

    async def register(
        self,
        email: str,
        password: str,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> User:  # type: ignore
        raise NotImplementedError("Not implemented")

    async def request_password_reset(self, email: str) -> dict[str, str]:
        raise NotImplementedError("Not implemented")

    async def send_reset_email(self, email: str) -> dict[str, str]:
        raise NotImplementedError("Not implemented")

    async def create_user_api_key(
        self,
        user_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict[str, str]:
        raise NotImplementedError("Not implemented")

    async def verify_email(
        self, email: str, verification_code: str
    ) -> dict[str, str]:
        raise NotImplementedError("Not implemented")

    async def send_verification_email(
        self, email: str, user: Optional[User] = None
    ) -> tuple[str, datetime]:
        raise NotImplementedError("Not implemented")

    async def list_user_api_keys(self, user_id: UUID) -> list[dict]:
        raise NotImplementedError("Not implemented")

    async def delete_user_api_key(self, user_id: UUID, key_id: UUID) -> bool:
        raise NotImplementedError("Not implemented")

    async def oauth_callback_handler(
        self, provider: str, oauth_id: str, email: str
    ) -> dict[str, Token]:
        raise NotImplementedError("Not implemented")
