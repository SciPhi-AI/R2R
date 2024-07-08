import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Assume these are imported from your existing modules
from ..abstractions.user import Token, TokenData, User, UserCreate
from .base import Provider, ProviderConfig


class AuthConfig(ProviderConfig):
    enabled: bool = True
    token_lifetime: int = 30

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r"]  # Add other providers as needed

    def validate(self) -> None:
        super().validate()


class AuthProvider(Provider, ABC):
    security = HTTPBearer()

    def __init__(self, config: AuthConfig):
        if not isinstance(config, AuthConfig):
            raise ValueError(
                "AuthProvider must be initialized with an AuthConfig"
            )
        super().__init__(config)

    @abstractmethod
    def get_password_hash(self, password: str) -> str:
        pass

    @abstractmethod
    def verify_password(
        self, plain_password: str, hashed_password: str
    ) -> bool:
        pass

    @abstractmethod
    def create_access_token(self, data: dict):
        pass

    @abstractmethod
    def decode_token(self, token: str):
        pass

    @abstractmethod
    def get_current_user(self, token: str):
        pass

    @abstractmethod
    def get_current_active_user(self, current_user: User):
        pass

    @abstractmethod
    def register_user(self, user: UserCreate):
        pass

    @abstractmethod
    def verify_email(self, verification_code: str):
        pass

    @abstractmethod
    def login(self, email: str, password: str):
        pass

    def auth_wrapper(self, auth: HTTPAuthorizationCredentials = Security(security)):
        return self.decode_token(auth.credentials)

