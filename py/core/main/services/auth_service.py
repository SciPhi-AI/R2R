import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from core.base import R2RException, Token
from core.base.api.models import User
from core.utils import generate_default_user_collection_id

from ..abstractions import R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger()


class AuthService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
    ):
        super().__init__(
            config,
            providers,
        )

    async def register(
        self,
        email: str,
        password: str,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
    ) -> User:
        return await self.providers.auth.register(
            email=email,
            password=password,
            name=name,
            bio=bio,
            profile_picture=profile_picture,
        )

    async def send_verification_email(
        self, email: str
    ) -> tuple[str, datetime]:
        return await self.providers.auth.send_verification_email(email=email)

    async def verify_email(
        self, email: str, verification_code: str
    ) -> dict[str, str]:
        if not self.config.auth.require_email_verification:
            raise R2RException(
                status_code=400, message="Email verification is not required"
            )

        user_id = await self.providers.database.users_handler.get_user_id_by_verification_code(
            verification_code
        )
        user = await self.providers.database.users_handler.get_user_by_id(
            user_id
        )
        if not user or user.email != email:
            raise R2RException(
                status_code=400, message="Invalid or expired verification code"
            )

        await self.providers.database.users_handler.mark_user_as_verified(
            user_id
        )
        await self.providers.database.users_handler.remove_verification_code(
            verification_code
        )
        return {"message": f"User account {user_id} verified successfully."}

    async def login(self, email: str, password: str) -> dict[str, Token]:
        return await self.providers.auth.login(email, password)

    async def user(self, token: str) -> User:
        token_data = await self.providers.auth.decode_token(token)
        if not token_data.email:
            raise R2RException(
                status_code=401, message="Invalid authentication credentials"
            )
        user = await self.providers.database.users_handler.get_user_by_email(
            token_data.email
        )
        if user is None:
            raise R2RException(
                status_code=401, message="Invalid authentication credentials"
            )
        return user

    async def refresh_access_token(
        self, refresh_token: str
    ) -> dict[str, Token]:
        return await self.providers.auth.refresh_access_token(refresh_token)

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> dict[str, str]:
        if not user:
            raise R2RException(status_code=404, message="User not found")
        return await self.providers.auth.change_password(
            user, current_password, new_password
        )

    async def request_password_reset(self, email: str) -> dict[str, str]:
        return await self.providers.auth.request_password_reset(email)

    async def confirm_password_reset(
        self, reset_token: str, new_password: str
    ) -> dict[str, str]:
        return await self.providers.auth.confirm_password_reset(
            reset_token, new_password
        )

    async def logout(self, token: str) -> dict[str, str]:
        return await self.providers.auth.logout(token)

    async def update_user(
        self,
        user_id: UUID,
        email: Optional[str] = None,
        is_superuser: Optional[bool] = None,
        name: Optional[str] = None,
        bio: Optional[str] = None,
        profile_picture: Optional[str] = None,
        limits_overrides: Optional[dict] = None,
        merge_limits: bool = False,
        new_metadata: Optional[dict] = None,
    ) -> User:
        user: User = (
            await self.providers.database.users_handler.get_user_by_id(user_id)
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
        if limits_overrides is not None:
            user.limits_overrides = limits_overrides
        return await self.providers.database.users_handler.update_user(
            user, merge_limits=merge_limits, new_metadata=new_metadata
        )

    async def delete_user(
        self,
        user_id: UUID,
        password: Optional[str] = None,
        delete_vector_data: bool = False,
        is_superuser: bool = False,
    ) -> dict[str, str]:
        user = await self.providers.database.users_handler.get_user_by_id(
            user_id
        )
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
                and password is not None
                and self.providers.auth.crypto_provider.verify_password(
                    plain_password=password,
                    hashed_password=user.hashed_password,
                )
            )
        ):
            raise R2RException(status_code=400, message="Incorrect password")
        await self.providers.database.users_handler.delete_user_relational(
            user_id
        )

        # Delete user's default collection
        # TODO: We need to better define what happens to the user's data when they are deleted
        collection_id = generate_default_user_collection_id(user_id)
        await self.providers.database.collections_handler.delete_collection_relational(
            collection_id
        )

        try:
            await self.providers.database.graphs_handler.delete(
                collection_id=collection_id,
            )
        except Exception as e:
            logger.warning(
                f"Error deleting graph for collection {collection_id}: {e}"
            )

        if delete_vector_data:
            await self.providers.database.chunks_handler.delete_user_vector(
                user_id
            )
            await self.providers.database.chunks_handler.delete_collection_vector(
                collection_id
            )

        return {"message": f"User account {user_id} deleted successfully."}

    async def clean_expired_blacklisted_tokens(
        self,
        max_age_hours: int = 7 * 24,
        current_time: Optional[datetime] = None,
    ):
        await self.providers.database.token_handler.clean_expired_blacklisted_tokens(
            max_age_hours, current_time
        )

    async def get_user_verification_code(
        self,
        user_id: UUID,
    ) -> dict:
        """Get only the verification code data for a specific user.

        This method should be called after superuser authorization has been
        verified.
        """
        verification_data = await self.providers.database.users_handler.get_user_validation_data(
            user_id=user_id
        )
        return {
            "verification_code": verification_data["verification_data"][
                "verification_code"
            ],
            "expiry": verification_data["verification_data"][
                "verification_code_expiry"
            ],
        }

    async def get_user_reset_token(
        self,
        user_id: UUID,
    ) -> dict:
        """Get only the verification code data for a specific user.

        This method should be called after superuser authorization has been
        verified.
        """
        verification_data = await self.providers.database.users_handler.get_user_validation_data(
            user_id=user_id
        )
        return {
            "reset_token": verification_data["verification_data"][
                "reset_token"
            ],
            "expiry": verification_data["verification_data"][
                "reset_token_expiry"
            ],
        }

    async def send_reset_email(self, email: str) -> dict:
        """Generate a new verification code and send a reset email to the user.
        Returns the verification code for testing/sandbox environments.

        Args:
            email (str): The email address of the user

        Returns:
            dict: Contains verification_code and message
        """
        return await self.providers.auth.send_reset_email(email)

    async def create_user_api_key(
        self, user_id: UUID, name: Optional[str], description: Optional[str]
    ) -> dict:
        """Generate a new API key for the user with optional name and
        description.

        Args:
            user_id (UUID): The ID of the user
            name (Optional[str]): Name of the API key
            description (Optional[str]): Description of the API key

        Returns:
            dict: Contains the API key and message
        """
        return await self.providers.auth.create_user_api_key(
            user_id=user_id, name=name, description=description
        )

    async def delete_user_api_key(self, user_id: UUID, key_id: UUID) -> bool:
        """Delete the API key for the user.

        Args:
            user_id (UUID): The ID of the user
            key_id (str): The ID of the API key

        Returns:
            bool: True if the API key was deleted successfully
        """
        return await self.providers.auth.delete_user_api_key(
            user_id=user_id, key_id=key_id
        )

    async def list_user_api_keys(self, user_id: UUID) -> list[dict]:
        """List all API keys for the user.

        Args:
            user_id (UUID): The ID of the user

        Returns:
            dict: Contains the list of API keys
        """
        return await self.providers.auth.list_user_api_keys(user_id)
