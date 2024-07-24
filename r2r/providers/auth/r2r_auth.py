import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from r2r.base import (
    AuthConfig,
    AuthProvider,
    CryptoProvider,
    DatabaseProvider,
    R2RException,
    Token,
    TokenData,
    User,
    UserCreate,
)

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
        super().__init__(config)
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
        try:
            user = self.register(
                UserCreate(
                    email=self.admin_email, password=self.admin_password
                )
            )
            self.db_provider.relational.mark_user_as_superuser(user.id)

        except R2RException:
            logger.info("Default admin user already exists.")

    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=self.access_token_lifetime_in_minutes
        )
        to_encode |= {"exp": expire.timestamp(), "token_type": "access"}
        return jwt.encode(to_encode, self.secret_key, algorithm="HS256")

    def create_refresh_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            days=self.refresh_token_lifetime_in_days
        )
        to_encode |= {"exp": expire, "token_type": "refresh"}
        return jwt.encode(to_encode, self.secret_key, algorithm="HS256")

    def decode_token(self, token: str) -> TokenData:
        try:
            # First, check if the token is blacklisted
            if self.db_provider.relational.is_token_blacklisted(token):
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

    def user(self, token: str = Depends(oauth2_scheme)) -> User:
        token_data = self.decode_token(token)
        user = self.db_provider.relational.get_user_by_email(token_data.email)
        if user is None:
            raise R2RException(
                status_code=401, message="Invalid authentication credentials"
            )
        return user

    def get_current_active_user(
        self, current_user: User = Depends(user)
    ) -> User:
        if not current_user.is_active:
            raise R2RException(status_code=400, message="Inactive user")
        return current_user

    def register(self, user: UserCreate) -> Dict[str, str]:
        # Check if user already exists
        if self.db_provider.relational.get_user_by_email(user.email):
            raise R2RException(
                status_code=400, message="Email already registered"
            )

        # Create new user
        new_user = self.db_provider.relational.create_user(user)

        if self.config.require_email_verification:
            # Generate verification code and send email
            verification_code = (
                self.crypto_provider.generate_verification_code()
            )
            expiry = datetime.now(timezone.utc) + timedelta(hours=24)

            self.db_provider.relational.store_verification_code(
                new_user.id, verification_code, expiry
            )
            new_user.verification_code_expiry = expiry
            # TODO - Integrate email provider(s)
            # self.providers.email.send_verification_email(new_user.email, verification_code)
        else:
            # Mark user as verified
            self.db_provider.relational.store_verification_code(
                new_user.id, None, None
            )
            self.db_provider.relational.mark_user_as_verified(new_user.id)

        return new_user

    def verify_email(self, verification_code: str) -> Dict[str, str]:
        user_id = self.db_provider.relational.get_user_id_by_verification_code(
            verification_code
        )
        if not user_id:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )
        self.db_provider.relational.mark_user_as_verified(user_id)
        self.db_provider.relational.remove_verification_code(verification_code)
        return {"message": "Email verified successfully"}

    def login(self, email: str, password: str) -> Dict[str, Token]:
        logger = logging.getLogger(__name__)
        logger.debug(f"Attempting login for email: {email}")

        user = self.db_provider.relational.get_user_by_email(email)
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

        logger.info(f"Successful login for user: {email}")
        access_token = self.create_access_token(data={"sub": user.email})
        refresh_token = self.create_refresh_token(data={"sub": user.email})
        return {
            "access_token": Token(token=access_token, token_type="access"),
            "refresh_token": Token(token=refresh_token, token_type="refresh"),
        }

    def refresh_access_token(
        self, user_email: str, refresh_token: str
    ) -> Dict[str, Token]:
        token_data = self.decode_token(refresh_token)
        if token_data.token_type != "refresh":
            raise R2RException(
                status_code=401, message="Invalid refresh token"
            )
        if token_data.email != user_email:
            raise R2RException(
                status_code=402,
                message="Invalid email address attached to token",
            )

        # Invalidate the old refresh token and create a new one
        self.db_provider.relational.blacklist_token(refresh_token)

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

    def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> Dict[str, str]:
        if not self.crypto_provider.verify_password(
            current_password, user.hashed_password
        ):
            raise R2RException(
                status_code=400, message="Incorrect current password"
            )

        hashed_new_password = self.crypto_provider.get_password_hash(
            new_password
        )
        self.db_provider.relational.update_user_password(
            user.id, hashed_new_password
        )
        return {"message": "Password changed successfully"}

    def request_password_reset(self, email: str) -> Dict[str, str]:
        user = self.db_provider.relational.get_user_by_email(email)
        if not user:
            # To prevent email enumeration, always return a success message
            return {
                "message": "If the email exists, a reset link has been sent"
            }

        reset_token = self.crypto_provider.generate_verification_code()
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        self.db_provider.relational.store_reset_token(
            user.id, reset_token, expiry
        )

        # TODO: Integrate with email provider to send reset link
        # self.email_provider.send_reset_email(email, reset_token)

        return {"message": "If the email exists, a reset link has been sent"}

    def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> Dict[str, str]:
        user_id = self.db_provider.relational.get_user_id_by_reset_token(
            reset_token
        )
        if not user_id:
            raise R2RException(
                status_code=400, message="Invalid or expired reset token"
            )

        hashed_new_password = self.crypto_provider.get_password_hash(
            new_password
        )
        self.db_provider.relational.update_user_password(
            user_id, hashed_new_password
        )
        self.db_provider.relational.remove_reset_token(user_id)
        return {"message": "Password reset successfully"}

    def logout(self, token: str) -> Dict[str, str]:
        # Add the token to a blacklist
        self.db_provider.relational.blacklist_token(token)
        return {"message": "Logged out successfully"}

    def clean_expired_blacklisted_tokens(self):
        self.db_provider.relational.clean_expired_blacklisted_tokens()
