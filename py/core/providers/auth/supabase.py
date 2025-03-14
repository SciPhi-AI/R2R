import logging
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from supabase import Client, create_client

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

logger = logging.getLogger()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class SupabaseAuthProvider(AuthProvider):
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
        self.supabase_url = config.extra_fields.get(
            "supabase_url", None
        ) or os.getenv("SUPABASE_URL")
        self.supabase_key = config.extra_fields.get(
            "supabase_key", None
        ) or os.getenv("SUPABASE_KEY")
        if not self.supabase_url or not self.supabase_key:
            raise HTTPException(
                status_code=500,
                detail="Supabase URL and key must be provided",
            )
        self.supabase: Client = create_client(
            self.supabase_url, self.supabase_key
        )

    async def initialize(self):
        # No initialization needed for Supabase
        pass

    def create_access_token(self, data: dict) -> str:
        raise NotImplementedError(
            "create_access_token is not used with Supabase authentication"
        )

    def create_refresh_token(self, data: dict) -> str:
        raise NotImplementedError(
            "create_refresh_token is not used with Supabase authentication"
        )

    async def decode_token(self, token: str) -> TokenData:
        raise NotImplementedError(
            "decode_token is not used with Supabase authentication"
        )

    async def register(
        self,
        email: str,
        password: str,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> User:  # type: ignore
        # Use Supabase client to create a new user

        if self.supabase.auth.sign_up(email=email, password=password):
            raise R2RException(
                status_code=400,
                message="Supabase provider implementation is still under construction",
            )
        else:
            raise R2RException(
                status_code=400, message="User registration failed"
            )

    async def send_verification_email(
        self, email: str, user: Optional[User] = None
    ) -> tuple[str, datetime]:
        raise NotImplementedError(
            "send_verification_email is not used with Supabase"
        )

    async def verify_email(
        self, email: str, verification_code: str
    ) -> dict[str, str]:
        # Use Supabase client to verify email
        if self.supabase.auth.verify_email(email, verification_code):
            return {"message": "Email verified successfully"}
        else:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

    async def login(self, email: str, password: str) -> dict[str, Token]:
        # Use Supabase client to authenticate user and get tokens
        if response := self.supabase.auth.sign_in(
            email=email, password=password
        ):
            access_token = response.access_token
            refresh_token = response.refresh_token
            return {
                "access_token": Token(token=access_token, token_type="access"),
                "refresh_token": Token(
                    token=refresh_token, token_type="refresh"
                ),
            }
        else:
            raise R2RException(
                status_code=401, message="Invalid email or password"
            )

    async def refresh_access_token(
        self, refresh_token: str
    ) -> dict[str, Token]:
        # Use Supabase client to refresh access token
        if response := self.supabase.auth.refresh_access_token(refresh_token):
            new_access_token = response.access_token
            new_refresh_token = response.refresh_token
            return {
                "access_token": Token(
                    token=new_access_token, token_type="access"
                ),
                "refresh_token": Token(
                    token=new_refresh_token, token_type="refresh"
                ),
            }
        else:
            raise R2RException(
                status_code=401, message="Invalid refresh token"
            )

    async def user(self, token: str = Depends(oauth2_scheme)) -> User:
        # Use Supabase client to get user details from token
        if user := self.supabase.auth.get_user(token).user:
            return User(
                id=user.id,
                email=user.email,
                is_active=True,  # Assuming active if exists in Supabase
                is_superuser=False,  # Default to False unless explicitly set
                created_at=user.created_at,
                updated_at=user.updated_at,
                is_verified=user.email_confirmed_at is not None,
                name=user.user_metadata.get("full_name"),
                # Set other optional fields if available in user metadata
            )

        else:
            raise R2RException(status_code=401, message="Invalid token")

    def get_current_active_user(
        self, current_user: User = Depends(user)
    ) -> User:
        # Check if user is active
        if not current_user.is_active:
            raise R2RException(status_code=400, message="Inactive user")
        return current_user

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> dict[str, str]:
        # Use Supabase client to update user password
        if self.supabase.auth.update(user.id, {"password": new_password}):
            return {"message": "Password changed successfully"}
        else:
            raise R2RException(
                status_code=400, message="Failed to change password"
            )

    async def request_password_reset(self, email: str) -> dict[str, str]:
        # Use Supabase client to send password reset email
        if self.supabase.auth.send_password_reset_email(email):
            return {
                "message": "If the email exists, a reset link has been sent"
            }
        else:
            raise R2RException(
                status_code=400, message="Failed to send password reset email"
            )

    async def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict[str, str]:
        # Use Supabase client to reset password with token
        if self.supabase.auth.reset_password_for_email(
            reset_token, new_password
        ):
            return {"message": "Password reset successfully"}
        else:
            raise R2RException(
                status_code=400, message="Invalid or expired reset token"
            )

    async def logout(self, token: str) -> dict[str, str]:
        # Use Supabase client to logout user and revoke token
        self.supabase.auth.sign_out(token)
        return {"message": "Logged out successfully"}

    async def clean_expired_blacklisted_tokens(self):
        # Not applicable for Supabase, tokens are managed by Supabase
        pass

    async def send_reset_email(self, email: str) -> dict[str, str]:
        raise NotImplementedError("send_reset_email is not used with Supabase")

    async def create_user_api_key(
        self,
        user_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict[str, str]:
        raise NotImplementedError(
            "API key management is not supported with Supabase authentication"
        )

    async def list_user_api_keys(self, user_id: UUID) -> list[dict]:
        raise NotImplementedError(
            "API key management is not supported with Supabase authentication"
        )

    async def delete_user_api_key(self, user_id: UUID, key_id: UUID) -> bool:
        raise NotImplementedError(
            "API key management is not supported with Supabase authentication"
        )

    async def oauth_callback_handler(
        self, provider: str, oauth_id: str, email: str
    ) -> dict[str, Token]:
        raise NotImplementedError(
            "API key management is not supported with Supabase authentication"
        )
