from datetime import datetime, timedelta
from typing import Optional

from r2r.base import (
    KVLoggingSingleton,
    R2RException,
    RunManager,
    Token,
    TokenData,
    User,
    UserCreate,
)
from r2r.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RPipelines, R2RProviders
from ..assembly.config import R2RConfig
from .base import Service


class AuthService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        run_manager: RunManager,
        logging_connection: KVLoggingSingleton,
    ):
        super().__init__(
            config, providers, pipelines, run_manager, logging_connection
        )

    @telemetry_event("RegisterUser")
    async def register(self, user: UserCreate) -> User:
        # Check if user already exists
        existing_user = self.providers.database.relational.get_user_by_email(
            user.email
        )
        if existing_user:
            raise R2RException(
                status_code=400, message="Email already registered"
            )

        # Create new user
        new_user = self.providers.database.relational.create_user(user)

        # Generate verification code and send email
        verification_code = (
            123456  # self.providers.auth.generate_verification_code()
        )
        expiry = datetime.utcnow() + timedelta(hours=24)

        self.providers.database.relational.store_verification_code(
            new_user.id, verification_code, expiry
        )
        # self.providers.email.send_verification_email(new_user.email, verification_code)

        return new_user

    @telemetry_event("VerifyEmail")
    async def verify_email(self, verification_code: str) -> bool:
        user_id = self.providers.database.relational.get_user_id_by_verification_code(
            verification_code
        )
        if not user_id:
            raise R2RException(
                status_code=400, message="Invalid verification code"
            )

        self.providers.database.relational.mark_user_as_verified(user_id)
        self.providers.database.relational.remove_verification_code(
            verification_code
        )
        return True

    @telemetry_event("Login")
    async def login(self, email: str, password: str) -> dict[str, Token]:
        return self.providers.auth.login(email, password)
        # user = self.providers.database.relational.get_user_by_email(email)
        # if not user or not self.providers.auth.crypto_provider.verify_password(
        #     password, user.hashed_password
        # ):
        #     raise R2RException(
        #         status_code=401, message="Incorrect email or password"
        #     )

        # if not user.is_verified:
        #     raise R2RException(status_code=401, message="Email not verified")

        # access_token = self.providers.auth.create_access_token(
        #     data={"sub": user.email}
        # )
        # return Token(access_token=access_token, token_type="access")

    @telemetry_event("GetCurrentUser")
    async def get_current_user(self, token: str) -> User:
        token_data = self.providers.auth.decode_token(token)
        user = self.providers.database.relational.get_user_by_email(
            token_data.email
        )
        if user is None:
            raise R2RException(
                status_code=401, message="Invalid authentication credentials"
            )
        return user

    @telemetry_event("RefreshToken")
    async def refresh_access_token(
        self, user_email: str, refresh_access_token: str
    ) -> dict[str, Token]:
        return self.providers.auth.refresh_access_token(
            user_email, refresh_access_token
        )
