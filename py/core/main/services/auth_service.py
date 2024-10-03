from datetime import datetime
from typing import Optional
from uuid import UUID

from core.base import R2RException, RunLoggingSingleton, RunManager, Token
from core.base.api.models import UserResponse
from core.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig
from .base import Service


class AuthService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipes: R2RPipes,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
        logging_connection: RunLoggingSingleton,
    ):
        super().__init__(
            config,
            providers,
            pipes,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

    @telemetry_event("RegisterUser")
    async def register(self, email: str, password: str) -> dict[str, str]:
        return await self.providers.auth.register(email, password)

    @telemetry_event("VerifyEmail")
    async def verify_email(
        self, email: str, verification_code: str
    ) -> dict[str, str]:
        if not self.config.auth.require_email_verification:
            raise R2RException(
                status_code=400, message="Email verification is not required"
            )

        user_id = await self.providers.database.relational.get_user_id_by_verification_code(
            verification_code
        )
        if not user_id:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

        user = await self.providers.database.relational.get_user_by_id(user_id)
        if not user or user.email != email:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

        await self.providers.database.relational.mark_user_as_verified(user_id)
        await self.providers.database.relational.remove_verification_code(
            verification_code
        )
        return {"message": f"User account {user_id} verified successfully."}

    @telemetry_event("Login")
    async def login(self, email: str, password: str) -> dict[str, Token]:
        return await self.providers.auth.login(email, password)

    @telemetry_event("GetCurrentUser")
    async def user(self, token: str) -> UserResponse:
        token_data = await self.providers.auth.decode_token(token)
        user = await self.providers.database.relational.get_user_by_email(
            token_data.email
        )
        if user is None:
            raise R2RException(
                status_code=401, message="Invalid authentication credentials"
            )
        return user

    @telemetry_event("RefreshToken")
    async def refresh_access_token(
        self, refresh_token: str
    ) -> dict[str, Token]:
        return await self.providers.auth.refresh_access_token(refresh_token)

    @telemetry_event("ChangePassword")
    async def change_password(
        self, user: UserResponse, current_password: str, new_password: str
    ) -> dict[str, str]:
        if not user:
            raise R2RException(status_code=404, message="User not found")
        return await self.providers.auth.change_password(
            user, current_password, new_password
        )

    @telemetry_event("RequestPasswordReset")
    async def request_password_reset(self, email: str) -> dict[str, str]:
        return await self.providers.auth.request_password_reset(email)

    @telemetry_event("ConfirmPasswordReset")
    async def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict[str, str]:
        return await self.providers.auth.confirm_password_reset(
            reset_token, new_password
        )

    @telemetry_event("Logout")
    async def logout(self, token: str) -> dict[str, str]:
        return await self.providers.auth.logout(token)

    @telemetry_event("UpdateUserProfile")
    async def update_user(
        self,
        user_id: UUID,
        email: Optional[str] = None,
        is_superuser: Optional[bool] = None,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> UserResponse:
        user: UserResponse = (
            await self.providers.database.relational.get_user_by_id(user_id)
        )
        if not user:
            raise R2RException(status_code=404, message="User not found")
        if email is not None:
            user.email = email
        if is_superuser is not None:
            user.is_superuser = is_superuser
        if name is not None:
            user.name = name
        if bio is not None:
            user.bio = bio
        if profile_picture is not None:
            user.profile_picture = profile_picture
        return await self.providers.database.relational.update_user(user)

    @telemetry_event("DeleteUserAccount")
    async def delete_user(
        self,
        user_id: UUID,
        password: str,
        delete_vector_data: bool = False,
        is_superuser: bool = False,
    ) -> dict[str, str]:
        user = await self.providers.database.relational.get_user_by_id(user_id)
        if not user:
            raise R2RException(status_code=404, message="User not found")
        if not (
            is_superuser
            or self.providers.auth.crypto_provider.verify_password(  # type: ignore
                password, user.hashed_password
            )
        ):
            raise R2RException(status_code=400, message="Incorrect password")
        await self.providers.database.relational.delete_user(user_id)
        if delete_vector_data:
            self.providers.database.vector.delete_user(user_id)

        return {"message": f"User account {user_id} deleted successfully."}

    @telemetry_event("CleanExpiredBlacklistedTokens")
    async def clean_expired_blacklisted_tokens(
        self,
        max_age_hours: int = 7 * 24,
        current_time: Optional[datetime] = None,
    ):
        await self.providers.database.relational.clean_expired_blacklisted_tokens(
            max_age_hours, current_time
        )
