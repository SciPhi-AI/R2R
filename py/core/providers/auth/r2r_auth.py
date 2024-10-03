import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

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

DEFAULT_ACCESS_LIFETIME_IN_MINUTES = 3600
DEFAULT_REFRESH_LIFETIME_IN_DAYS = 7

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

DEFAULT_R2R_SK = "wNFbczH3QhUVcPALwtWZCPi0lrDlGV3P1DPRVEQCPbM"


class R2RAuthProvider(AuthProvider):
    def __init__(
        self,
        config: AuthConfig,
        crypto_provider: CryptoProvider,
        db_provider: DatabaseProvider,
    ):
        super().__init__(config, crypto_provider)
        logger.debug(f"Initializing R2RAuthProvider with config: {config}")
        self.crypto_provider = crypto_provider
        self.db_provider = db_provider
        self.secret_key = (
            config.secret_key or os.getenv("R2R_SECRET_KEY") or DEFAULT_R2R_SK
        )
        self.access_token_lifetime_in_minutes = (
            config.access_token_lifetime_in_minutes
            or os.getenv("R2R_ACCESS_LIFE_IN_MINUTES")
        )
        self.refresh_token_lifetime_in_days = (
            config.refresh_token_lifetime_in_days
            or os.getenv("R2R_REFRESH_LIFE_IN_MINUTES")
        )
        self.config: AuthConfig = config

    async def initialize(self):
        try:
            user = await self.register(
                email=self.admin_email, password=self.admin_password
            )
            await self.db_provider.relational.mark_user_as_superuser(user.id)
        except R2RException:
            logger.info("Default admin user already exists.")

    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=float(
                self.access_token_lifetime_in_minutes
                or DEFAULT_ACCESS_LIFETIME_IN_MINUTES
            )
        )
        to_encode |= {"exp": expire.timestamp(), "token_type": "access"}
        return jwt.encode(to_encode, self.secret_key, algorithm="HS256")

    def create_refresh_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            days=float(
                self.refresh_token_lifetime_in_days
                or DEFAULT_REFRESH_LIFETIME_IN_DAYS
            )
        )
        to_encode |= {"exp": expire, "token_type": "refresh"}
        return jwt.encode(to_encode, self.secret_key, algorithm="HS256")

    async def decode_token(self, token: str) -> TokenData:
        try:
            # First, check if the token is blacklisted
            if await self.db_provider.relational.is_token_blacklisted(token):
                raise R2RException(
                    status_code=401, message="Token has been invalidated"
                )

            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            email: str = payload.get("sub")
            token_type: str = payload.get("token_type")
            exp: float = payload.get("exp")
            exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
            if (
                email is None
                or token_type is None
                or exp is None
                or exp_datetime < datetime.now(timezone.utc)
            ):
                raise R2RException(status_code=401, message="Invalid token")
            return TokenData(
                email=email, token_type=token_type, exp=exp_datetime
            )
        except jwt.ExpiredSignatureError as e:
            raise R2RException(
                status_code=401, message="Token has expired"
            ) from e
        except jwt.InvalidTokenError as e:
            raise R2RException(status_code=401, message="Invalid token") from e

    async def user(self, token: str = Depends(oauth2_scheme)) -> UserResponse:
        token_data = await self.decode_token(token)
        user = await self.db_provider.relational.get_user_by_email(
            token_data.email
        )
        if user is None:
            raise R2RException(
                status_code=401, message="Invalid authentication credentials"
            )
        return user

    def get_current_active_user(
        self, current_user: UserResponse = Depends(user)
    ) -> UserResponse:
        if not current_user.is_active:
            raise R2RException(status_code=400, message="Inactive user")
        return current_user

    async def register(self, email: str, password: str) -> Dict[str, str]:
        # Create new user and give them a default collection
        new_user = await self.db_provider.relational.create_user(
            email, password
        )
        default_collection = (
            await self.db_provider.relational.create_default_collection(
                new_user.id,
            )
        )

        await self.db_provider.relational.add_user_to_collection(
            new_user.id, default_collection.collection_id
        )

        if self.config.require_email_verification:
            # Generate verification code and send email
            verification_code = (
                self.crypto_provider.generate_verification_code()
            )
            expiry = datetime.now(timezone.utc) + timedelta(hours=24)

            await self.db_provider.relational.store_verification_code(
                new_user.id, verification_code, expiry
            )
            new_user.verification_code_expiry = expiry
            # TODO - Integrate email provider(s)
            # self.providers.email.send_verification_email(new_user.email, verification_code)
        else:
            # Mark user as verified
            await self.db_provider.relational.store_verification_code(
                new_user.id, None, None
            )
            await self.db_provider.relational.mark_user_as_verified(
                new_user.id
            )

        return new_user

    async def verify_email(
        self, email: str, verification_code: str
    ) -> dict[str, str]:
        user_id = (
            await self.db_provider.relational.get_user_id_by_verification_code(
                verification_code
            )
        )
        if not user_id:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )
        await self.db_provider.relational.mark_user_as_verified(user_id)
        await self.db_provider.relational.remove_verification_code(
            verification_code
        )
        return {"message": "Email verified successfully"}

    async def login(self, email: str, password: str) -> Dict[str, Token]:
        logger = logging.getLogger(__name__)
        logger.debug(f"Attempting login for email: {email}")

        user = await self.db_provider.relational.get_user_by_email(email)
        if not user:
            logger.warning(f"No user found for email: {email}")
            raise R2RException(
                status_code=401, message="Incorrect email or password"
            )

        logger.debug(f"User found: {user}")

        if not isinstance(user.hashed_password, str):
            logger.error(
                f"Invalid hashed_password type: {type(user.hashed_password)}"
            )
            raise R2RException(
                status_code=500, message="Invalid password hash in database"
            )

        try:
            password_verified = self.crypto_provider.verify_password(
                password, user.hashed_password
            )
        except Exception as e:
            logger.error(f"Error during password verification: {str(e)}")
            raise R2RException(
                status_code=500, message="Error during password verification"
            ) from e

        if not password_verified:
            logger.warning(f"Invalid password for user: {email}")
            raise R2RException(
                status_code=401, message="Incorrect email or password"
            )

        if not user.is_verified:
            logger.warning(f"Unverified user attempted login: {email}")
            raise R2RException(status_code=401, message="Email not verified")

        access_token = self.create_access_token(data={"sub": user.email})
        refresh_token = self.create_refresh_token(data={"sub": user.email})
        return {
            "access_token": Token(token=access_token, token_type="access"),
            "refresh_token": Token(token=refresh_token, token_type="refresh"),
        }

    async def refresh_access_token(
        self, refresh_token: str
    ) -> Dict[str, Token]:
        token_data = await self.decode_token(refresh_token)
        if token_data.token_type != "refresh":
            raise R2RException(
                status_code=401, message="Invalid refresh token"
            )

        # Invalidate the old refresh token and create a new one
        await self.db_provider.relational.blacklist_token(refresh_token)

        new_access_token = self.create_access_token(
            data={"sub": token_data.email}
        )
        new_refresh_token = self.create_refresh_token(
            data={"sub": token_data.email}
        )
        return {
            "access_token": Token(token=new_access_token, token_type="access"),
            "refresh_token": Token(
                token=new_refresh_token, token_type="refresh"
            ),
        }

    async def change_password(
        self, user: UserResponse, current_password: str, new_password: str
    ) -> Dict[str, str]:
        if not isinstance(user.hashed_password, str):
            logger.error(
                f"Invalid hashed_password type: {type(user.hashed_password)}"
            )
            raise R2RException(
                status_code=500, message="Invalid password hash in database"
            )

        if not self.crypto_provider.verify_password(
            current_password, user.hashed_password
        ):
            raise R2RException(
                status_code=400, message="Incorrect current password"
            )

        hashed_new_password = self.crypto_provider.get_password_hash(
            new_password
        )
        await self.db_provider.relational.update_user_password(
            user.id, hashed_new_password
        )
        return {"message": "Password changed successfully"}

    async def request_password_reset(self, email: str) -> Dict[str, str]:
        user = await self.db_provider.relational.get_user_by_email(email)
        if not user:
            # To prevent email enumeration, always return a success message
            return {
                "message": "If the email exists, a reset link has been sent"
            }

        reset_token = self.crypto_provider.generate_verification_code()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        await self.db_provider.relational.store_reset_token(
            user.id, reset_token, expiry
        )

        # TODO: Integrate with email provider to send reset link
        # self.email_provider.send_reset_email(email, reset_token)

        return {"message": "If the email exists, a reset link has been sent"}

    async def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> Dict[str, str]:
        user_id = await self.db_provider.relational.get_user_id_by_reset_token(
            reset_token
        )
        if not user_id:
            raise R2RException(
                status_code=400, message="Invalid or expired reset token"
            )

        hashed_new_password = self.crypto_provider.get_password_hash(
            new_password
        )
        await self.db_provider.relational.update_user_password(
            user_id, hashed_new_password
        )
        await self.db_provider.relational.remove_reset_token(user_id)
        return {"message": "Password reset successfully"}

    async def logout(self, token: str) -> Dict[str, str]:
        # Add the token to a blacklist
        await self.db_provider.relational.blacklist_token(token)
        return {"message": "Logged out successfully"}

    async def clean_expired_blacklisted_tokens(self):
        await self.db_provider.relational.clean_expired_blacklisted_tokens()
