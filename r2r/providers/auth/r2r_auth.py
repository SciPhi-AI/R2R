import logging
import os
from datetime import datetime, timedelta
from typing import Dict

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from r2r.base import (
    AuthConfig,
    AuthProvider,
    CryptoProvider,
    DatabaseProvider,
    Token,
    TokenData,
    User,
    UserCreate,
)

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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
        self.secret_key = config.secret_key or os.getenv("R2R_SECRET_KEY")
        self.access_token_lifetime_in_minutes = (
            config.access_token_lifetime_in_minutes
            or os.getenv("R2R_TOKEN_LIFE_IN_MINUTES")
        )
        self.refresh_token_lifetime_in_days = (
            config.refresh_token_lifetime_in_days
            or os.getenv("R2R_TOKEN_LIFE_IN_DAYS")
        )

    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(
            minutes=self.access_token_lifetime_in_minutes
        )
        to_encode.update({"exp": expire, "token_type": "access"})
        print("to_encode = ", to_encode)
        print("self.secret_key = ", self.secret_key)
        return jwt.encode(to_encode, self.secret_key, algorithm="HS256")

    def create_refresh_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(
            days=self.refresh_token_lifetime_in_days
        )
        to_encode.update({"exp": expire, "token_type": "refresh"})
        return jwt.encode(to_encode, self.secret_key, algorithm="HS256")

    def decode_token(self, token: str) -> TokenData:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            email: str = payload.get("sub")
            token_type: str = payload.get("token_type")
            if email is None or token_type is None:
                raise HTTPException(status_code=401, detail="Invalid token")
            return TokenData(email=email, token_type=token_type)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def get_current_user(self, token: str = Depends(oauth2_scheme)) -> User:
        token_data = self.decode_token(token)
        user = self.db_provider.relational.get_user_by_email(token_data.email)
        if user is None:
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )
        return user

    def get_current_active_user(
        self, current_user: User = Depends(get_current_user)
    ) -> User:
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user

    def register(self, user: UserCreate) -> Dict[str, str]:
        existing_user = self.db_provider.relational.get_user_by_email(
            user.email
        )
        if existing_user:
            raise HTTPException(
                status_code=400, detail="Email already registered"
            )
        hashed_password = self.crypto_provider.get_password_hash(user.password)
        verification_code = self.crypto_provider.generate_verification_code()
        new_user = User(
            email=user.email,
            hashed_password=hashed_password,
            is_active=True,
            is_verified=False,
        )
        created_user = self.db_provider.relational.create_user(new_user)
        self.db_provider.relational.store_verification_code(
            created_user.id,
            verification_code,
            datetime.utcnow() + timedelta(hours=24),
        )
        # Send verification email here
        return {
            "message": "User created. Please check your email for verification."
        }

    def verify_email(self, verification_code: str) -> Dict[str, str]:
        user_id = self.db_provider.relational.get_user_id_by_verification_code(
            verification_code
        )
        if not user_id:
            raise HTTPException(
                status_code=400, detail="Invalid or expired verification code"
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
            raise HTTPException(
                status_code=401, detail="Incorrect email or password"
            )

        logger.debug(f"User found: {user}")

        if not isinstance(password, str):
            logger.error(f"Invalid password type: {type(password)}")
            raise HTTPException(
                status_code=400, detail="Invalid password format"
            )

        if not isinstance(user.hashed_password, str):
            logger.error(
                f"Invalid hashed_password type: {type(user.hashed_password)}"
            )
            raise HTTPException(
                status_code=500, detail="Invalid password hash in database"
            )

        try:
            password_verified = self.crypto_provider.verify_password(
                password, user.hashed_password
            )
        except Exception as e:
            logger.error(f"Error during password verification: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Error during password verification"
            )

        if not password_verified:
            logger.warning(f"Invalid password for user: {email}")
            raise HTTPException(
                status_code=401, detail="Incorrect email or password"
            )

        if not user.is_verified:
            logger.warning(f"Unverified user attempted login: {email}")
            raise HTTPException(status_code=401, detail="Email not verified")

        logger.info(f"Successful login for user: {email}")
        access_token = self.create_access_token(data={"sub": user.email})
        refresh_access_token = self.create_refresh_token(
            data={"sub": user.email}
        )
        return {
            "access_token": Token(token=access_token, token_type="access"),
            "refresh_access_token": Token(
                token=refresh_access_token, token_type="refresh"
            ),
        }

    def refresh_access_token(
        self, user_email: str, refresh_access_token: str
    ) -> Dict[str, Token]:
        token_data = self.decode_token(refresh_access_token)
        if token_data.token_type != "refresh":
            raise HTTPException(
                status_code=401, detail="Invalid refresh token"
            )
        if token_data.email != user_email:
            raise HTTPException(
                status_code=401, detail="Invalid refresh token"
            )
        # TODO - Implement refresh token tracking
        # Verify if the refresh token is still valid in the database
        # if not self.is_refresh_token_valid(token_data.email, refresh_access_token):
        #     raise HTTPException(status_code=401, detail="Refresh token has been revoked")
        # Invalidate the old refresh token and create a new one
        # self.invalidate_refresh_token(token_data.email, refresh_access_token)
        new_access_token = self.create_access_token(
            data={"sub": token_data.email}
        )
        new_refresh_token = self.create_refresh_token(
            data={"sub": token_data.email}
        )
        return {
            "access_token": Token(token=new_access_token, token_type="access"),
            "refresh_access_token": Token(
                token=new_refresh_token, token_type="refresh"
            ),
        }
