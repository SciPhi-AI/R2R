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
        try:
            data = {"name": name} if name else {}
            if bio:
                data["bio"] = bio
            if profile_picture:
                data["profile_picture"]=profile_picture
            
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": data
                }
            })
            
            user_data = response.user
            if user_data:
                return User(
                    id=user_data.id,
                    email=user_data.email,
                    is_active=True,
                    is_superuser=False,
                    created_at=user_data.created_at,
                    updated_at=user_data.updated_at,
                    is_verified=user_data.email_confirmed_at is not None,
                    name=name,
                    bio=bio,
                    profile_picture=profile_picture,
                )
            else:
                raise R2RException(
                    status_code=400, message="User registration failed"
                )
        except Exception as e:
            logger.error(f"Error during registration: {str(e)}")
            raise R2RException(
                status_code=400, message=f"User registration failed: {str(e)}"
            ) from e

    async def send_verification_email(
        self, email: str, user: Optional[User] = None
    ) -> tuple[str, datetime]:
        try:
            self.supabase.auth.resend_confirmation_email(email)
            # Since Supabase handles the verification code, we return a dummy value
            return "verification_handled_by_supabase", datetime.now()
        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
            raise R2RException(
                status_code=400, message=f"Failed to send verification email: {str(e)}"
            ) from e

    async def verify_email(
        self, email: str, verification_code: str
    ) -> dict[str, str]:
        # Email verification is handled by Supabase through email links
        raise NotImplementedError(
            "Email verification is handled directly by Supabase through email links"
        )

    async def login(self, email: str, password: str) -> dict[str, Token]:
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            session = response.session
            if not session:
                raise R2RException(
                    status_code=401, message="Invalid email or password"
                )
            
            access_token = session.access_token
            refresh_token = session.refresh_token
            
            return {
                "access_token": Token(token=access_token, token_type="access"),
                "refresh_token": Token(
                    token=refresh_token, token_type="refresh"
                ),
            }
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise R2RException(
                status_code=401, message="Invalid email or password"
            ) from e

    async def refresh_access_token(
        self, refresh_token: str
    ) -> dict[str, Token]:
        try:
            response = self.supabase.auth.refresh_session({
                "refresh_token": refresh_token
            })
            
            session = response.session
            if not session:
                raise R2RException(
                    status_code=401, message="Invalid refresh token"
                )
            
            new_access_token = session.access_token
            new_refresh_token = session.refresh_token
            
            return {
                "access_token": Token(
                    token=new_access_token, token_type="access"
                ),
                "refresh_token": Token(
                    token=new_refresh_token, token_type="refresh"
                ),
            }
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise R2RException(
                status_code=401, message="Invalid refresh token"
            ) from e

    async def user(self, token: str = Depends(oauth2_scheme)) -> User:
        try:
            # Set the auth token for the client session
            self.supabase.auth.set_session(token)
            
            # Get the user data
            user_response = self.supabase.auth.get_user()
            user_data = user_response.user
            
            if not user_data:
                raise R2RException(status_code=401, message="Invalid token")
            
            user_metadata = user_data.user_metadata or {}
            
            return User(
                id=user_data.id,
                email=user_data.email,
                is_active=True,  # Assuming active if exists in Supabase
                is_superuser=False,  # Default to False unless explicitly set
                created_at=user_data.created_at,
                updated_at=user_data.updated_at,
                is_verified=user_data.email_confirmed_at is not None,
                name=user_metadata.get("name"),
                bio=user_metadata.get("bio"),
                profile_picture=user_metadata.get("profile_picture"),
            )
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            raise R2RException(status_code=401, message="Invalid token") from e

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
        try:
            # First verify current password by attempting to sign in
            self.supabase.auth.sign_in_with_password({
                "email": user.email,
                "password": current_password
            })
            
            # Then update the password
            self.supabase.auth.update_user({
                "password": new_password
            })
            
            return {"message": "Password changed successfully"}
        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            raise R2RException(
                status_code=400, message="Failed to change password"
            ) from e

    async def request_password_reset(self, email: str) -> dict[str, str]:
        try:
            self.supabase.auth.reset_password_for_email(email)
            return {
                "message": "If the email exists, a reset link has been sent"
            }
        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}")
            # Return the same message regardless of success to prevent email enumeration
            return {
                "message": "If the email exists, a reset link has been sent"
            }

    async def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict[str, str]:
        # In Supabase, this is usually handled via their hosted UI
        # This method would be called after the user clicks the reset link
        try:
            self.supabase.auth.set_session(reset_token)
            self.supabase.auth.update_user({
                "password": new_password
            })
            return {"message": "Password reset successfully"}
        except Exception as e:
            logger.error(f"Password reset confirmation error: {str(e)}")
            raise R2RException(
                status_code=400, message="Invalid or expired reset token"
            ) from e

    async def logout(self, token: str) -> dict[str, str]:
        try:
            self.supabase.auth.set_session(token)
            self.supabase.auth.sign_out()
            return {"message": "Logged out successfully"}
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            # Even if there's an error, we consider the user logged out
            return {"message": "Logged out successfully"}

    async def clean_expired_blacklisted_tokens(self):
        # Not applicable for Supabase, tokens are managed by Supabase
        pass

    async def send_reset_email(self, email: str) -> dict[str, str]:
        # This is handled by request_password_reset
        return await self.request_password_reset(email)

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
        # This would require implementation specific to your OAuth flow with Supabase
        raise NotImplementedError(
            "OAuth callback handling needs custom implementation with Supabase"
        )
