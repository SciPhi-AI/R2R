import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from fastapi import Security
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from ..abstractions import R2RException, Token, TokenData
from ..api.models import User
from .base import Provider, ProviderConfig
from .crypto import CryptoProvider
from .email import EmailProvider

logger = logging.getLogger()

if TYPE_CHECKING:
    from core.providers.database import PostgresDatabaseProvider

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


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
    database_provider: "PostgresDatabaseProvider"

    def __init__(
        self,
        config: AuthConfig,
        crypto_provider: CryptoProvider,
        database_provider: "PostgresDatabaseProvider",
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
        self.config: AuthConfig = config
        self.database_provider: "PostgresDatabaseProvider" = database_provider

    async def _get_default_admin_user(self) -> User:
        return await self.database_provider.users_handler.get_user_by_email(
            self.admin_email
        )

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
    async def send_verification_email(
        self, email: str, user: Optional[User] = None
    ) -> tuple[str, datetime]:
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

    def auth_wrapper(
        self,
        public: bool = False,
    ):
        async def _auth_wrapper(
            auth: Optional[HTTPAuthorizationCredentials] = Security(
                self.security
            ),
            api_key: Optional[str] = Security(api_key_header),
        ) -> User:
            # If authentication is not required and no credentials are provided, return the default admin user
            if (
                ((not self.config.require_authentication) or public)
                and auth is None
                and api_key is None
            ):
                return await self._get_default_admin_user()
            if not auth and not api_key:
                raise R2RException(
                    message="No credentials provided. Create an account at https://app.sciphi.ai and set your API key using `r2r configure key` OR change your base URL to a custom deployment.",
                    status_code=401,
                )
            if auth and api_key:
                raise R2RException(
                    message="Cannot have both Bearer token and API key",
                    status_code=400,
                )
            # 1. Try JWT if `auth` is present (Bearer token)
            if auth is not None:
                credentials = auth.credentials
                try:
                    token_data = await self.decode_token(credentials)
                    user = await self.database_provider.users_handler.get_user_by_email(
                        token_data.email
                    )
                    if user is not None:
                        return user
                except R2RException:
                    # JWT decoding failed for logical reasons (invalid token)
                    pass
                except Exception as e:
                    # JWT decoding failed unexpectedly, log and continue
                    logger.debug(f"JWT verification failed: {e}")

                # 2. If JWT failed, try API key from Bearer token
                # Expected format: key_id.raw_api_key
                if "." in credentials:
                    key_id, raw_api_key = credentials.split(".", 1)
                    api_key_record = await self.database_provider.users_handler.get_api_key_record(
                        key_id
                    )
                    if api_key_record is not None:
                        hashed_key = api_key_record["hashed_key"]
                        if self.crypto_provider.verify_api_key(
                            raw_api_key, hashed_key
                        ):
                            user = await self.database_provider.users_handler.get_user_by_id(
                                api_key_record["user_id"]
                            )
                            if user is not None and user.is_active:
                                return user

            # 3. If no Bearer token worked, try the X-API-Key header
            if api_key is not None and "." in api_key:
                key_id, raw_api_key = api_key.split(".", 1)
                api_key_record = await self.database_provider.users_handler.get_api_key_record(
                    key_id
                )
                if api_key_record is not None:
                    hashed_key = api_key_record["hashed_key"]
                    if self.crypto_provider.verify_api_key(
                        raw_api_key, hashed_key
                    ):
                        user = await self.database_provider.users_handler.get_user_by_id(
                            api_key_record["user_id"]
                        )
                        if user is not None and user.is_active:
                            return user

            # If we reach here, both JWT and API key auth failed
            raise R2RException(
                message="Invalid token or API key",
                status_code=401,
            )

        return _auth_wrapper

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
