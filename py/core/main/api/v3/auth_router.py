from typing import Optional, Union
from uuid import UUID

from fastapi import Body, Depends, Path
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import EmailStr

from core.base import R2RException
from core.base.api.models import (
    GenericMessageResponse,
    WrappedGenericMessageResponse,
    WrappedResetDataResult,
    WrappedTokenResponse,
    WrappedUserResponse,
    WrappedVerificationResult,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from ....base.logger.base import RunType
from ...services.auth_service import AuthService
from .base_router import BaseRouterV3

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class AuthRouter(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: Union[
            HatchetOrchestrationProvider, SimpleOrchestrationProvider
        ],
        run_type: RunType = RunType.UNSPECIFIED,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

        self.services = services  # for type hinting

    def _setup_routes(self):
        @self.router.post("/register", response_model=WrappedUserResponse)
        @self.base_endpoint
        async def register_app(
            email: EmailStr = Body(..., description="User's email address"),
            password: str = Body(..., description="User's password"),
        ):
            """
            Register a new user with the given email and password.
            """
            result = await self.services["auth"].register(email, password)
            return result

        @self.router.post(
            "/verify_email", response_model=WrappedGenericMessageResponse
        )
        @self.base_endpoint
        async def verify_email_app(
            email: EmailStr = Body(..., description="User's email address"),
            verification_code: str = Body(
                ..., description="Email verification code"
            ),
        ):
            """
            Verify a user's email address.

            This endpoint is used to confirm a user's email address using the verification code
            sent to their email after registration.
            """
            result = await self.services["auth"].verify_email(
                email, verification_code
            )
            return GenericMessageResponse(message=result["message"])

        @self.router.post("/login", response_model=WrappedTokenResponse)
        @self.base_endpoint
        async def login_app(
            form_data: OAuth2PasswordRequestForm = Depends(),
        ):
            """
            Authenticate a user and provide access tokens.

            This endpoint authenticates a user using their email (username) and password,
            and returns access and refresh tokens upon successful authentication.
            """
            login_result = await self.services["auth"].login(
                form_data.username, form_data.password
            )
            return login_result

        @self.router.post(
            "/logout", response_model=WrappedGenericMessageResponse
        )
        @self.base_endpoint
        async def logout_app(
            token: str = Depends(oauth2_scheme),
            auth_user=Depends(
                self.services["auth"].providers.auth.auth_wrapper
            ),
        ):
            """
            Log out the current user.

            This endpoint invalidates the user's current access token, effectively logging them out.
            """
            result = await self.services["auth"].logout(token)
            return GenericMessageResponse(message=result["message"])

        @self.router.get("/user", response_model=WrappedUserResponse)
        @self.base_endpoint
        async def get_user_app(
            auth_user=Depends(
                self.services["auth"].providers.auth.auth_wrapper
            ),
        ):
            """
            Get the current user's profile information.

            This endpoint returns the profile information of the currently authenticated user.
            """
            return auth_user

        @self.router.put("/user", response_model=WrappedUserResponse)
        @self.base_endpoint
        async def put_user_app(
            user_id: UUID = Body(None, description="ID of the user to update"),
            email: EmailStr | None = Body(
                None, description="Updated email address"
            ),
            is_superuser: bool | None = Body(
                None, description="Updated superuser status"
            ),
            name: str | None = Body(None, description="Updated user name"),
            bio: str | None = Body(None, description="Updated user bio"),
            profile_picture: str | None = Body(
                None, description="Updated profile picture URL"
            ),
            auth_user=Depends(
                self.services["auth"].providers.auth.auth_wrapper
            ),
        ):
            """
            Update the current user's profile information.

            This endpoint allows the authenticated user to update their profile information.
            """

            if is_superuser is not None and not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can update the superuser status of a user",
                    403,
                )
            if not auth_user.is_superuser:
                if not auth_user.id == user_id:
                    raise R2RException(
                        "Only superusers can update other users' information",
                        403,
                    )

            return await self.services["auth"].update_user(
                user_id=user_id,
                email=email,
                is_superuser=is_superuser,
                name=name,
                bio=bio,
                profile_picture=profile_picture,
            )

        @self.router.post(
            "/refresh_access_token", response_model=WrappedTokenResponse
        )
        @self.base_endpoint
        async def refresh_access_token_app(
            refresh_token: str = Body(..., description="Refresh token")
        ):
            """
            Refresh the access token using a refresh token.

            This endpoint allows users to obtain a new access token using their refresh token.
            """
            refresh_result = await self.services["auth"].refresh_access_token(
                refresh_token=refresh_token,
            )
            return refresh_result

        @self.router.post(
            "/change_password", response_model=WrappedGenericMessageResponse
        )
        @self.base_endpoint
        async def change_password_app(
            current_password: str = Body(..., description="Current password"),
            new_password: str = Body(..., description="New password"),
            auth_user=Depends(
                self.services["auth"].providers.auth.auth_wrapper
            ),
        ):
            """
            Change the authenticated user's password.

            This endpoint allows users to change their password by providing their current password
            and a new password.
            """
            result = await self.services["auth"].change_password(
                auth_user,
                current_password,
                new_password,
            )
            return GenericMessageResponse(message=result["message"])

        @self.router.post(
            "/request_password_reset",
            response_model=WrappedGenericMessageResponse,
        )
        @self.base_endpoint
        async def request_password_reset_app(
            email: EmailStr = Body(..., description="User's email address")
        ):
            """
            Request a password reset for a user.

            This endpoint initiates the password reset process by sending a reset link
            to the specified email address.
            """
            result = await self.services["auth"].request_password_reset(email)
            return GenericMessageResponse(message=result["message"])

        @self.router.post(
            "/reset_password",
            response_model=WrappedGenericMessageResponse,
        )
        @self.base_endpoint
        async def reset_password_app(
            reset_token: str = Body(..., description="Password reset token"),
            new_password: str = Body(..., description="New password"),
        ):
            result = await self.services["auth"].confirm_password_reset(
                reset_token, new_password
            )
            return GenericMessageResponse(message=result["message"])

        @self.router.delete(
            "/user/{user_id}", response_model=WrappedGenericMessageResponse
        )
        @self.base_endpoint
        async def delete_user_app(
            user_id: str = Path(..., description="ID of the user to delete"),
            password: Optional[str] = Body(
                None, description="User's current password"
            ),
            delete_vector_data: Optional[bool] = Body(
                False,
                description="Whether to delete the user's vector data",
            ),
            auth_user=Depends(
                self.services["auth"].providers.auth.auth_wrapper
            ),
        ):
            """
            Delete a user account.

            This endpoint allows users to delete their own account or, for superusers,
            to delete any user account.
            """
            if str(auth_user.id) != user_id and not auth_user.is_superuser:
                raise Exception("User ID does not match authenticated user")
            if not auth_user.is_superuser and not password:
                raise Exception("Password is required for non-superusers")
            user_uuid = UUID(user_id)
            result = await self.services["auth"].delete_user(
                user_uuid, password, delete_vector_data
            )
            return GenericMessageResponse(message=result["message"])

        @self.router.get("/user/{user_id}/verification_data")
        @self.base_endpoint
        async def get_user_verification_code(
            user_id: str = Path(..., description="User ID"),
            auth_user=Depends(
                self.services["auth"].providers.auth.auth_wrapper
            ),
        ) -> WrappedVerificationResult:
            """
            Get only the verification code for a specific user.
            Only accessible by superusers.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    status_code=403,
                    message="Only superusers can access verification codes",
                )

            try:
                user_uuid = UUID(user_id)
            except ValueError:
                raise R2RException(
                    status_code=400, message="Invalid user ID format"
                )
            result = await self.services["auth"].get_user_verification_code(
                user_uuid
            )
            return result

        @self.router.get("/user/{user_id}/reset_token")
        @self.base_endpoint
        async def get_user_reset_token(
            user_id: str = Path(..., description="User ID"),
            auth_user=Depends(
                self.services["auth"].providers.auth.auth_wrapper
            ),
        ) -> WrappedResetDataResult:
            """
            Get only the verification code for a specific user.
            Only accessible by superusers.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    status_code=403,
                    message="Only superusers can access verification codes",
                )

            try:
                user_uuid = UUID(user_id)
            except ValueError:
                raise R2RException(
                    status_code=400, message="Invalid user ID format"
                )
            result = await self.services["auth"].get_user_reset_token(
                user_uuid
            )
            if not result["reset_token"]:
                raise R2RException(
                    status_code=404, message="No reset token found"
                )
            return result

        # Add to AuthRouter class (auth_router.py)
        @self.router.post(
            "/send_reset_email", response_model=WrappedVerificationResult
        )
        @self.base_endpoint
        async def send_reset_email_app(
            email: EmailStr = Body(..., description="User's email address"),
        ):
            """
            Generate a new verification code and send a reset email to the user.
            Returns the verification code and success message.

            This endpoint is particularly useful for sandbox/testing environments
            where direct access to verification codes is needed.
            """
            result = await self.services["auth"].send_reset_email(email)
            return result
