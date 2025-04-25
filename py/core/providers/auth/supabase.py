import logging
import os
from datetime import datetime, timedelta, timezone
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
        try:
            # Remove the "Bearer " prefix (if present)
            if token.startswith("Bearer "):
                token = token[7:]

            # Get Supabase token information
            auth_response = await self.supabase.auth.get_user(token)
            
            if not auth_response or not auth_response.user:
                raise R2RException(status_code=401, message="Invalid token")
            
            user = auth_response.user
            
            # Default expiration time
            # If Supabase session expire information is not available, use the current time plus 1 hour
            expiration_time = datetime.now(timezone.utc) + timedelta(hours=1)
            
            # If Supabase session_expires_at information is available, use it
            if hasattr(auth_response, "session") and hasattr(auth_response.session, "expires_at"):
                # If expires_at is a timestamp, convert it to a datetime
                expiration_time = datetime.fromtimestamp(auth_response.session.expires_at, timezone.utc)
            
            # Create TokenData object
            token_data = TokenData(
                email=user.email,
                token_type="access",  # Supabase JWT is considered an access token
                exp=expiration_time
            )
            
            return token_data
        
        except Exception as e:
            logger.error(f"Token decode error: {str(e)}")
            raise R2RException(status_code=401, message="Invalid token")

    async def register(
        self,
        email: str,
        password: str,
        is_verified: bool = False,
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
        try:
            response = await self.supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            # Correct access method - token information is found in response.session
            if response.session:
                access_token = response.session.access_token
                refresh_token = response.session.refresh_token
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
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            raise R2RException(
                status_code=401, message="Invalid email or password"
            )

    async def refresh_access_token(
        self, refresh_token: str
    ) -> dict[str, Token]:
        # Use Supabase client to refresh access token
        try:
            response = await self.supabase.auth.refresh_session(refresh_token)
            if response.session:
                new_access_token = response.session.access_token
                new_refresh_token = response.session.refresh_token
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
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise R2RException(
                status_code=401, message="Invalid refresh token"
            )

    async def user(self, token: str = Depends(oauth2_scheme)) -> User:
        # Use Supabase client to get user details from token
        try:
            auth_response = await self.supabase.auth.get_user(token)
            if auth_response.user:
                user_data = auth_response.user
                return User(
                    id=user_data.id,
                    email=user_data.email,
                    is_active=True,  # Assuming active if exists in Supabase
                    is_superuser=False,  # Default to False unless explicitly set
                    created_at=user_data.created_at,
                    updated_at=user_data.updated_at or user_data.created_at,
                    is_verified=user_data.email_confirmed_at is not None,
                    name=user_data.user_metadata.get("name"),
                    # Set other optional fields if available in user metadata
                )
            else:
                raise R2RException(status_code=401, message="Invalid token")
        except Exception as e:
            logger.error(f"User lookup error: {str(e)}")
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
        try:
            # First, we log in with the current password to verify the user
            await self.supabase.auth.sign_in_with_password({
                "email": user.email,
                "password": current_password
            })
            # Then we update the password
            await self.supabase.auth.update_user({"password": new_password})
            return {"message": "Password changed successfully"}
        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            raise R2RException(
                status_code=400, message="Failed to change password"
            )

    async def request_password_reset(self, email: str) -> dict[str, str]:
        # Use Supabase client to send password reset email
        try:
            # Find the base URL from the environment variable
            base_url = os.getenv("R2R_BASE_URL")
            if base_url:
                # If R2R_BASE_URL is set, change the port from 7272 to 7273
                # Add /auth/login to the end of the URL
                # Remove the trailing slash from the URL
                if base_url.endswith("/"):
                    base_url = base_url[:-1]
                # Change the port from 7272 to 7273
                if ":7272" in base_url:
                    redirect_url = base_url.replace(":7272", ":7273")
                else:
                    redirect_url = base_url
                # Add /auth/login to the end of the URL
                if not redirect_url.endswith("/auth/login"):
                    redirect_url = f"{redirect_url}/auth/login"
            else:
                # Use the default URL
                redirect_url = "https://app.sciphi.ai/auth/login"            
            # Send the password reset email and use the custom redirect URL
            await self.supabase.auth.reset_password_for_email(
                email, 
                options={"redirect_to": redirect_url}
            )
            # Return a success message for security reasons
            return {
                "message": "If the email exists, a reset link has been sent"
            }
        except Exception as e:
            # Even if an error occurs, log the error and return a success message
            logger.error(f"Password reset request error: {str(e)}")
            return {
                "message": "If the email exists, a reset link has been sent"
            }

    async def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict[str, str]:
        raise NotImplementedError(
            "Password reset confirmation is not implemented with Supabase authentication"
        )

    async def logout(self, token: str = None) -> dict[str, str]:
        try:
            # Logout the user
            await self.supabase.auth.sign_out()
            return {"message": "Logged out successfully"}
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            raise R2RException(
                status_code=400, message="Logout failed"
            )

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
