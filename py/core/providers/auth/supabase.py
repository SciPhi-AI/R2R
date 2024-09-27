import logging
import os

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from supabase import Client, create_client

from core.base import (
    AuthConfig,
    AuthProvider,
    CryptoProvider,
    DatabaseProvider,
    R2RException,
    Token,
    TokenData,
)
from core.base.api.models import UserResponse

logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class SupabaseAuthProvider(AuthProvider):
    def __init__(
        self,
        config: AuthConfig,
        crypto_provider: CryptoProvider,
        db_provider: DatabaseProvider,
    ):
        super().__init__(config, crypto_provider)
        self.supabase_url = config.extra_fields.get(
            "supabase_url", None
        ) or os.getenv("SUPABASE_URL")
        self.supabase_key = config.extra_fields.get(
            "supabase_key", None
        ) or os.getenv("SUPABASE_KEY")
        if not self.supabase_url or not self.supabase_key:
            raise R2RException(
                status_code=500,
                message="Supabase URL and key must be provided",
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

    async def register(self, email: str, password: str) -> dict[str, str]:
        # Use Supabase client to create a new user
        user = self.supabase.auth.sign_up(email=email, password=password)

        if user:
            return {"message": "User registered successfully"}
        else:
            raise R2RException(
                status_code=400, message="User registration failed"
            )

    async def verify_email(
        self, email: str, verification_code: str
    ) -> dict[str, str]:
        # Use Supabase client to verify email
        response = self.supabase.auth.verify_email(email, verification_code)

        if response:
            return {"message": "Email verified successfully"}
        else:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

    async def login(self, email: str, password: str) -> dict[str, Token]:
        # Use Supabase client to authenticate user and get tokens
        response = self.supabase.auth.sign_in(email=email, password=password)
        if response:
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
        response = self.supabase.auth.refresh_access_token(refresh_token)

        if response:
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

    async def user(self, token: str = Depends(oauth2_scheme)) -> UserResponse:
        # Use Supabase client to get user details from token
        user = self.supabase.auth.get_user(token).user
        if user:
            return UserResponse(
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
        self, current_user: UserResponse = Depends(user)
    ) -> UserResponse:
        # Check if user is active
        if not current_user.is_active:
            raise R2RException(status_code=400, message="Inactive user")
        return current_user

    async def change_password(
        self, user: UserResponse, current_password: str, new_password: str
    ) -> dict[str, str]:
        # Use Supabase client to update user password
        response = self.supabase.auth.update(
            user.id, {"password": new_password}
        )

        if response:
            return {"message": "Password changed successfully"}
        else:
            raise R2RException(
                status_code=400, message="Failed to change password"
            )

    async def request_password_reset(self, email: str) -> dict[str, str]:
        # Use Supabase client to send password reset email
        response = self.supabase.auth.send_password_reset_email(email)

        if response:
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
        response = self.supabase.auth.reset_password_for_email(
            reset_token, new_password
        )

        if response:
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
