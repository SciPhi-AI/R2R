import os
import secrets
import string
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from r2r.base import (
    CryptoProvider,
    AuthConfig,
    AuthProvider,
    DatabaseProvider,
    TokenData,
    User,
    UserCreate,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class R2RAuthProvider(AuthProvider):
    def __init__(self, config: AuthConfig, crypto_provider:CryptoProvider, db_provider: DatabaseProvider,  *args, **kwargs):
        self.crypto_provider = crypto_provider
        self.config = config
        self.secret_key = config.secret_key or os.getenv("R2R_SECRET_KEY")
        if not self.secret_key:
            raise ValueError("Secret key not set")

        self.token_lifetime = config.token_lifetime or int(
            os.getenv("R2R_TOKEN_LIFETIME")
        )
        if not self.token_lifetime:
            raise ValueError("Token lifetime not set")

        self.db_provider = db_provider
        super().__init__(config)

    def get_password_hash(self, password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def verify_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    def create_access_token(self, data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.token_lifetime)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm="HS256")

    def decode_token(self, token: str):
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            email: str = payload.get("sub")
            if email is None:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authentication credentials",
                )
            return TokenData(email=email)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def get_current_user(self, token: str = Depends(oauth2_scheme)):
        token_data = self.decode_token(token)
        user = self.db_provider.relational.get_user_by_email(token_data.email)
        if user is None:
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )
        return user

    def get_current_active_user(
        self, current_user: User = Depends(get_current_user)
    ):
        if not current_user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user

    def register_user(self, user: UserCreate):
        existing_user = self.db_provider.relational.get_user_by_email(
            user.email
        )
        if existing_user:
            raise HTTPException(
                status_code=400, detail="Email already registered"
            )
        hashed_password = self.get_password_hash(user.password)
        verification_code = self.generate_verification_code()
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

    def verify_email(self, verification_code: str):
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

    def login(self, email: str, password: str):
        user = self.db_provider.relational.get_user_by_email(email)
        if not user or not self.verify_password(
            password, user.hashed_password
        ):
            raise HTTPException(
                status_code=401, detail="Incorrect email or password"
            )
        if not user.is_verified:
            raise HTTPException(status_code=401, detail="Email not verified")
        access_token = self.create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}

    def generate_verification_code(self, length: int = 32) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def generate_secret_key(length: int = 32) -> str:
        """
        Generate a secure random secret key.

        Args:
            length (int): The length of the secret key. Defaults to 32.

        Returns:
            str: A secure random secret key.
        """
        return secrets.token_urlsafe(length)
