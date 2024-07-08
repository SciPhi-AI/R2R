import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from r2r.base import AuthConfig, AuthProvider, TokenData, User, UserCreate

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class R2RAuthProvider(AuthProvider):
    def __init__(self, config: AuthConfig):
        self.config = config

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
        user = (
            self.db_session.query(User)
            .filter(User.email == token_data.email)
            .first()
        )
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
        db_user = (
            self.db_session.query(User)
            .filter(User.email == user.email)
            .first()
        )
        if db_user:
            raise HTTPException(
                status_code=400, detail="Email already registered"
            )
        hashed_password = self.get_password_hash(user.password)
        verification_code = str(uuid.uuid4())
        new_user = User(
            email=user.email,
            hashed_password=hashed_password,
            verification_code=verification_code,
            verification_code_expiry=datetime.utcnow() + timedelta(hours=24),
        )
        self.db_session.add(new_user)
        self.db_session.commit()
        # Send verification email here
        return {
            "message": "User created. Please check your email for verification."
        }

    def verify_email(self, verification_code: str):
        user = (
            self.db_session.query(User)
            .filter(User.verification_code == verification_code)
            .first()
        )
        if not user or user.verification_code_expiry < datetime.utcnow():
            raise HTTPException(
                status_code=400, detail="Invalid or expired verification code"
            )
        user.is_verified = True
        user.verification_code = None
        user.verification_code_expiry = None
        self.db_session.commit()
        return {"message": "Email verified successfully"}

    def login(self, email: str, password: str):
        user = self.db_session.query(User).filter(User.email == email).first()
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