from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
import bcrypt
import jwt
import uuid

from .base import Provider, ProviderConfig

# Assume these are imported from your existing modules
from ..abstractions.user import User, UserCreate, Token, TokenData

class AuthConfig(ProviderConfig):
    secret_key: str
    token_lifetime: int = 30

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r"]  # Add other providers as needed

    def validate(self) -> None:
        super().validate()
        if not self.secret_key:
            raise ValueError("Secret key is required")

class AuthProvider(Provider, ABC):
    def __init__(self, config: AuthConfig):
        if not isinstance(config, AuthConfig):
            raise ValueError("AuthProvider must be initialized with an AuthConfig")
        super().__init__(config)

    @abstractmethod
    def get_password_hash(self, password: str) -> str:
        pass

    @abstractmethod
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
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
