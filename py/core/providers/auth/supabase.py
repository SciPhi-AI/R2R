import logging
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer, HTTPAuthorizationCredentials
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
        self.security = None  # This would need to be properly defined

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
        # Get user from Supabase
        try:
            user_response = self.supabase.auth.get_user(token)
            user = user_response.user
            if not user:
                raise R2RException(status_code=401, message="Invalid token")
            
            # Create TokenData with user information
            return TokenData(
                email=user.email,
                sub=str(user.id),
                exp=None  # Supabase handles token expiration
            )
        except Exception as e:
            logger.error(f"Error decoding token: {str(e)}")
            raise R2RException(status_code=401, message="Invalid token")

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
            user_metadata = {}
            if name:
                user_metadata["full_name"] = name
            if bio:
                user_metadata["bio"] = bio
            if profile_picture:
                user_metadata["profile_picture"] = profile_picture

            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": user_metadata
                } if user_metadata else None
            })
            
            if response.user:
                # Convert Supabase user to our User model
                return User(
                    id=response.user.id,
                    email=response.user.email,
                    is_active=True,
                    is_superuser=False,
                    created_at=response.user.created_at,
                    updated_at=response.user.updated_at,
                    is_verified=response.user.email_confirmed_at is not None,
                    name=user_metadata.get("full_name"),
                    bio=user_metadata.get("bio"),
                    profile_picture=user_metadata.get("profile_picture"),
                )
            else:
                raise R2RException(
                    status_code=400, message="User registration failed"
                )
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            raise R2RException(
                status_code=400, message=f"User registration failed: {str(e)}"
            )

    async def send_verification_email(
        self, email: str, user: Optional[User] = None
    ) -> tuple[str, datetime]:
        # Supabase handles email verification automatically during sign-up
        # This method can be used to resend the verification email
        try:
            self.supabase.auth.resend({
                "type": "signup",
                "email": email,
                "options": {
                    "email_redirect_to": f"{self.config.site_url}/verify-email"
                }
            })
            # Return a placeholder verification code and expiry
            # In reality, Supabase handles this internally
            return "verification_handled_by_supabase", datetime.now()
        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
            raise R2RException(
                status_code=400, message=f"Failed to send verification email: {str(e)}"
            )

    async def verify_email(
        self, email: str, verification_code: str
    ) -> dict[str, str]:
        # Use Supabase client to verify email with OTP
        try:
            response = self.supabase.auth.verify_otp({
                "email": email,
                "token": verification_code,
                "type": "email"
            })
            
            if response.user:
                return {"message": "Email verified successfully"}
            else:
                raise R2RException(
                    status_code=400, message="Invalid or expired verification code"
                )
        except Exception as e:
            logger.error(f"Email verification error: {str(e)}")
            raise R2RException(
                status_code=400, message=f"Email verification failed: {str(e)}"
            )

    async def login(self, email: str, password: str) -> dict[str, Token]:
        # Use Supabase client to authenticate user and get tokens
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
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
            response = self.supabase.auth.refresh_session(refresh_token)
            
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
            response = self.supabase.auth.get_user(token)
            user = response.user
            
            if user:
                return User(
                    id=user.id,
                    email=user.email,
                    is_active=True,  # Assuming active if exists in Supabase
                    is_superuser=False,  # Default to False unless explicitly set
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                    is_verified=user.email_confirmed_at is not None,
                    name=user.user_metadata.get("full_name"),
                    bio=user.user_metadata.get("bio"),
                    profile_picture=user.user_metadata.get("profile_picture"),
                )
            else:
                raise R2RException(status_code=401, message="Invalid token")
        except Exception as e:
            logger.error(f"User retrieval error: {str(e)}")
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
            # First verify the current password by attempting to sign in
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
            )

    async def request_password_reset(self, email: str) -> dict[str, str]:
        # Use Supabase client to send password reset email
        try:
            self.supabase.auth.reset_password_for_email(
                email,
                {
                    "redirect_to": f"{self.config.site_url}/reset-password"
                }
            )
            return {
                "message": "If the email exists, a reset link has been sent"
            }
        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}")
            # Return success even if email doesn't exist for security reasons
            return {
                "message": "If the email exists, a reset link has been sent"
            }

    async def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict[str, str]:
        # Use Supabase client to reset password with token
        try:
            # In Supabase, the user would have the reset token in their session
            # after clicking the reset link, so we just need to update the password
            self.supabase.auth.update_user({
                "password": new_password
            })
            return {"message": "Password reset successfully"}
        except Exception as e:
            logger.error(f"Password reset confirmation error: {str(e)}")
            raise R2RException(
                status_code=400, message="Invalid or expired reset token"
            )

    async def logout(self, token: str) -> dict[str, str]:
        # Use Supabase client to logout user and revoke token
        try:
            self.supabase.auth.sign_out()
            return {"message": "Logged out successfully"}
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            raise R2RException(
                status_code=400, message="Failed to logout"
            )

    async def clean_expired_blacklisted_tokens(self):
        # Not applicable for Supabase, tokens are managed by Supabase
        pass

    async def send_reset_email(self, email: str) -> dict[str, str]:
        # This is an alias for request_password_reset
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
        raise NotImplementedError(
            "OAuth callback handling is not implemented with Supabase authentication"
        )
