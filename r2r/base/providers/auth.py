from abc import ABC, abstractmethod
from typing import Dict, Optional

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..abstractions.user import Token, TokenData, User, UserCreate
from .base import Provider, ProviderConfig


class AuthConfig(ProviderConfig):
    enabled: bool = True
    secret_key: Optional[str] = None
    access_token_lifetime_in_minutes: Optional[int] = None
    refresh_token_lifetime_in_days: Optional[int] = None

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
    def create_access_token(self, data: dict) -> str:
        pass

    @abstractmethod
    def create_refresh_token(self, data: dict) -> str:
        pass

    @abstractmethod
    def decode_token(self, token: str) -> TokenData:
        pass

    @abstractmethod
    def get_current_user(self, token: str) -> User:
        pass

    @abstractmethod
    def get_current_active_user(self, current_user: User) -> User:
        pass

    @abstractmethod
    def register(self, user: UserCreate) -> Dict[str, str]:
        pass

    @abstractmethod
    def verify_email(self, verification_code: str) -> Dict[str, str]:
        pass

    @abstractmethod
    def login(self, email: str, password: str) -> Dict[str, Token]:
        pass

    @abstractmethod
    def refresh_access_token(
        self, user_email: str, refresh_access_token: str
    ) -> Dict[str, str]:
        pass

    def auth_wrapper(
        self, auth: HTTPAuthorizationCredentials = Security(security)
    ):
        return self.decode_token(auth.credentials)
