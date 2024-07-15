from abc import ABC, abstractmethod
from typing import Dict, Optional

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..abstractions.exception import R2RException
from ..abstractions.user import Token, TokenData, User, UserCreate
from ..utils import generate_id_from_label
from .base import Provider, ProviderConfig


class AuthConfig(ProviderConfig):
    secret_key: Optional[str] = None
    require_authentication: Optional[bool] = False
    require_email_verification: Optional[bool] = False
    access_token_lifetime_in_minutes: Optional[int] = None
    refresh_token_lifetime_in_days: Optional[int] = None
    default_admin_email: Optional[str] = "admin@example.com"
    default_admin_password: Optional[str] = "password123"

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r"]

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

    async def auth_wrapper(
        self, auth: Optional[HTTPAuthorizationCredentials] = Security(security)
    ) -> User:
        if not self.config.require_authentication and auth is None:
            return self.default_admin_user

        if auth is None:
            raise R2RException(
                status_code=401, detail="Authentication required"
            )

        try:
            token_data = self.decode_token(auth.credentials)
            user = self.get_current_user(token_data.email)
            return user
        except Exception as e:
            raise R2RException(
                status_code=401, detail="Invalid authentication credentials"
            )
