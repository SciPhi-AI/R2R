import logging
from abc import ABC, abstractmethod
from typing import Optional

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..abstractions import R2RException, Token, TokenData
from ..api.models import User
from .base import Provider, ProviderConfig
from .crypto import CryptoProvider
from .database import DatabaseProvider
from .email import EmailProvider

logger = logging.getLogger()


class AuthConfig(ProviderConfig):
    secret_key: Optional[str] = None
    require_authentication: bool = False
    require_email_verification: bool = False
    default_admin_email: str = "admin@example.com"
    default_admin_password: str = "change_me_immediately"
    access_token_lifetime_in_minutes: Optional[int] = None
    refresh_token_lifetime_in_days: Optional[int] = None

    @property
    def supported_providers(self) -> list[str]:
        return ["r2r"]

    def validate_config(self) -> None:
        pass


class AuthProvider(Provider, ABC):
    security = HTTPBearer(auto_error=False)
    crypto_provider: CryptoProvider
    email_provider: EmailProvider
    database_provider: DatabaseProvider

    def __init__(
        self,
        config: AuthConfig,
        crypto_provider: CryptoProvider,
        database_provider: DatabaseProvider,
        email_provider: EmailProvider,
    ):
        if not isinstance(config, AuthConfig):
            raise ValueError(
                "AuthProvider must be initialized with an AuthConfig"
            )
        self.config = config
        self.admin_email = config.default_admin_email
        self.admin_password = config.default_admin_password
        self.crypto_provider = crypto_provider
        self.database_provider = database_provider
        self.email_provider = email_provider
        super().__init__(config)
        self.config: AuthConfig = config  # for type hinting

    async def _get_default_admin_user(self) -> User:
        return await self.database_provider.get_user_by_email(self.admin_email)

    @abstractmethod
    def create_access_token(self, data: dict) -> str:
        pass

    @abstractmethod
    def create_refresh_token(self, data: dict) -> str:
        pass

    @abstractmethod
    async def decode_token(self, token: str) -> TokenData:
        pass

    @abstractmethod
    async def user(self, token: str) -> User:
        pass

    @abstractmethod
    def get_current_active_user(self, current_user: User) -> User:
        pass

    @abstractmethod
    async def register(self, email: str, password: str) -> User:
        pass

    @abstractmethod
    async def verify_email(
        self, email: str, verification_code: str
    ) -> dict[str, str]:
        pass

    @abstractmethod
    async def login(self, email: str, password: str) -> dict[str, Token]:
        pass

    @abstractmethod
    async def refresh_access_token(
        self, refresh_token: str
    ) -> dict[str, Token]:
        pass

    async def auth_wrapper(
        self, auth: Optional[HTTPAuthorizationCredentials] = Security(security)
    ) -> User:
        if not self.config.require_authentication and auth is None:
            return await self._get_default_admin_user()

        if auth is None:
            raise R2RException(
                message="Authentication required.",
                status_code=401,
            )

        try:
            return await self.user(auth.credentials)
        except Exception as e:
            raise R2RException(
                message=f"Error '{e}' occurred during authentication.",
                status_code=401,
            )

    @abstractmethod
    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> dict[str, str]:
        pass

    @abstractmethod
    async def request_password_reset(self, email: str) -> dict[str, str]:
        pass

    @abstractmethod
    async def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict[str, str]:
        pass

    @abstractmethod
    async def logout(self, token: str) -> dict[str, str]:
        pass

    @abstractmethod
    async def send_reset_email(self, email: str) -> dict[str, str]:
        pass
