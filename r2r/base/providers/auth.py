import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..abstractions.exception import R2RException
from ..abstractions.user import Token, TokenData, User, UserCreate
from .base import Provider, ProviderConfig

logger = logging.getLogger(__name__)


class AuthConfig(ProviderConfig):
    secret_key: Optional[str] = None
    require_authentication: Optional[bool] = False
    require_email_verification: Optional[bool] = False
    access_token_lifetime_in_minutes: Optional[int] = None
    refresh_token_lifetime_in_days: Optional[int] = None
    default_admin_email: Optional[str] = "admin@example.com"
    default_admin_password: Optional[str] = "change_me_immediately"

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r"]

    def validate(self) -> None:
        super().validate()


class AuthProvider(Provider, ABC):
    security = HTTPBearer(auto_error=False)

    def __init__(self, config: AuthConfig):
        if not isinstance(config, AuthConfig):
            raise ValueError(
                "AuthProvider must be initialized with an AuthConfig"
            )
        self.config = config
        self.admin_email = config.default_admin_email
        self.admin_password = config.default_admin_password
        super().__init__(config)

    def _get_default_admin_user(self) -> User:
        return User(
            email=self.admin_email,
            hashed_password=self.crypto_provider.get_password_hash(
                self.admin_password
            ),
            is_superuser=True,
            is_active=True,
            is_verified=True,
        )

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
    def user(self, token: str) -> User:
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
            return self._get_default_admin_user()

        if auth is None:
            raise R2RException(
                message="Authentication required.",
                status_code=401,
            )

        try:
            user = self.user(auth.credentials)
            return user
        except Exception as e:
            raise R2RException(
                message=f"Error '{e}' occured during authentication.",
                status_code=401,
            )
