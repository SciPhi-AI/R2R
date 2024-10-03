from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import EmailStr

from core.base import R2RException
from core.base.api.models import (
    GenericMessageResponse,
    WrappedGenericMessageResponse,
    WrappedTokenResponse,
    WrappedUserResponse,
)
from core.base.providers import OrchestrationProvider

from ..services.auth_service import AuthService
from .base_router import BaseRouter, RunType

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class AuthRouter(BaseRouter):
    def __init__(
        self,
        service: AuthService,
        orchestration_provider: OrchestrationProvider,
        run_type: RunType = RunType.UNSPECIFIED,
    ):
        super().__init__(service, orchestration_provider, run_type)
        self.service: AuthService = service  # for type hinting

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
            result = await self.service.register(email, password)
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
            result = await self.service.verify_email(email, verification_code)
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
            login_result = await self.service.login(
                form_data.username, form_data.password
            )
            return login_result

        @self.router.post(
            "/logout", response_model=WrappedGenericMessageResponse
        )
        @self.base_endpoint
        async def logout_app(
            token: str = Depends(oauth2_scheme),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            """
            Log out the current user.

            This endpoint invalidates the user's current access token, effectively logging them out.
            """
            result = await self.service.logout(token)
            return GenericMessageResponse(message=result["message"])

        @self.router.get("/user", response_model=WrappedUserResponse)
        @self.base_endpoint
        async def get_user_app(
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            """
            Get the current user's profile information.

            This endpoint returns the profile information of the currently authenticated user.
            """
            return auth_user

        @self.router.put("/user", response_model=WrappedUserResponse)
        @self.base_endpoint
        async def put_user_app(
            user_id: str = Body(None, description="ID of the user to update"),
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
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
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

            try:
                user_uuid = UUID(user_id)
            except ValueError:
                raise R2RException(
                    status_code=400, message="Invalid user ID format."
                )

            return await self.service.update_user(
                user_id=user_uuid,
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
            refresh_result = await self.service.refresh_access_token(
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
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            """
            Change the authenticated user's password.

            This endpoint allows users to change their password by providing their current password
            and a new password.
            """
            result = await self.service.change_password(
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
            result = await self.service.request_password_reset(email)
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
            result = await self.service.confirm_password_reset(
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
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
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
            result = await self.service.delete_user(
                user_uuid, password, delete_vector_data
            )
            return GenericMessageResponse(message=result["message"])
