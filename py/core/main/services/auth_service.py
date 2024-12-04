from datetime import datetime
from typing import Optional
from uuid import UUID

from core.base import R2RException, RunManager, Token
from core.base.api.models import User
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider
from core.telemetry.telemetry_decorator import telemetry_event
from core.utils import generate_default_user_collection_id

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
        logging_connection: SqlitePersistentLoggingProvider,
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
    async def register(self, email: str, password: str) -> User:
        return await self.providers.auth.register(email, password)

    @telemetry_event("VerifyEmail")
    async def verify_email(
        self, email: str, verification_code: str
    ) -> dict[str, str]:
        if not self.config.auth.require_email_verification:
            raise R2RException(
                status_code=400, message="Email verification is not required"
            )

        user_id = (
            await self.providers.database.get_user_id_by_verification_code(
                verification_code
            )
        )
        if not user_id:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

        user = await self.providers.database.get_user_by_id(user_id)
        if not user or user.email != email:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

        await self.providers.database.mark_user_as_verified(user_id)
        await self.providers.database.remove_verification_code(
            verification_code
        )
        return {"message": f"User account {user_id} verified successfully."}

    @telemetry_event("Login")
    async def login(self, email: str, password: str) -> dict[str, Token]:
        return await self.providers.auth.login(email, password)

    @telemetry_event("GetCurrentUser")
    async def user(self, token: str) -> User:
        token_data = await self.providers.auth.decode_token(token)
        if not token_data.email:
            raise R2RException(
                status_code=401, message="Invalid authentication credentials"
            )
        user = await self.providers.database.get_user_by_email(
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
        self, user: User, current_password: str, new_password: str
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
    ) -> User:
        user: User = await self.providers.database.get_user_by_id(user_id)
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
        return await self.providers.database.update_user(user)

    @telemetry_event("DeleteUserAccount")
    async def delete_user(
        self,
        user_id: UUID,
        password: Optional[str] = None,
        delete_vector_data: bool = False,
        is_superuser: bool = False,
    ) -> dict[str, str]:
        user = await self.providers.database.get_user_by_id(user_id)
        if not user:
            raise R2RException(status_code=404, message="User not found")
        if not is_superuser and not password:
            raise R2RException(
                status_code=422, message="Password is required for deletion"
            )
        if not (
            is_superuser
            or (
                user.hashed_password is not None
                and self.providers.auth.crypto_provider.verify_password(
                    password, user.hashed_password  # type: ignore
                )
            )
        ):
            raise R2RException(status_code=400, message="Incorrect password")
        await self.providers.database.delete_user_relational(user_id)

        # Delete user's default collection
        # TODO: We need to better define what happens to the user's data when they are deleted
        collection_id = generate_default_user_collection_id(user_id)
        await self.providers.database.delete_collection_relational(
            collection_id
        )

        if delete_vector_data:
            await self.providers.database.delete_user_vector(user_id)
            await self.providers.database.delete_collection_vector(
                collection_id
            )

        return {"message": f"User account {user_id} deleted successfully."}

    @telemetry_event("CleanExpiredBlacklistedTokens")
    async def clean_expired_blacklisted_tokens(
        self,
        max_age_hours: int = 7 * 24,
        current_time: Optional[datetime] = None,
    ):
        await self.providers.database.clean_expired_blacklisted_tokens(
            max_age_hours, current_time
        )

    @telemetry_event("GetUserVerificationCode")
    async def get_user_verification_code(
        self,
        user_id: UUID,
    ) -> dict:
        """
        Get only the verification code data for a specific user.
        This method should be called after superuser authorization has been verified.
        """
        verification_data = (
            await self.providers.database.get_user_validation_data(
                user_id=user_id
            )
        )
        return {
            "verification_code": verification_data["verification_data"][
                "verification_code"
            ],
            "expiry": verification_data["verification_data"][
                "verification_code_expiry"
            ],
        }

    @telemetry_event("GetUserVerificationCode")
    async def get_user_reset_token(
        self,
        user_id: UUID,
    ) -> dict:
        """
        Get only the verification code data for a specific user.
        This method should be called after superuser authorization has been verified.
        """
        verification_data = (
            await self.providers.database.get_user_validation_data(
                user_id=user_id
            )
        )
        return {
            "reset_token": verification_data["verification_data"][
                "reset_token"
            ],
            "expiry": verification_data["verification_data"][
                "reset_token_expiry"
            ],
        }

    @telemetry_event("SendResetEmail")
    async def send_reset_email(self, email: str) -> dict:
        """
        Generate a new verification code and send a reset email to the user.
        Returns the verification code for testing/sandbox environments.

        Args:
            email (str): The email address of the user

        Returns:
            dict: Contains verification_code and message
        """
        return await self.providers.auth.send_reset_email(email)
