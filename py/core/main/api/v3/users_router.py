import textwrap
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import EmailStr

from core.base import R2RException
from core.base.api.models import (
    GenericBooleanResponse,
    GenericMessageResponse,
    WrappedBooleanResponse,
    WrappedCollectionsResponse,
    WrappedGenericMessageResponse,
    WrappedTokenResponse,
    WrappedUserResponse,
    WrappedUsersResponse,
)

from .base_router import BaseRouterV3

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class UsersRouter(BaseRouterV3):
    def __init__(
        self, providers, services, orchestration_provider=None, run_type=None
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _setup_routes(self):

        # New authentication routes
        @self.router.post(
            "/users/register",
            response_model=WrappedUserResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            new_user = client.users.register(
                                email="jane.doe@example.com",
                                password="secure_password123"
                            )"""
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.register({
                                    email: "jane.doe@example.com",
                                    password: "secure_password123"
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r users register jane.doe@example.com secure_password123
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/users/register" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "email": "jane.doe@example.com",
                                    "password": "secure_password123"
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def register(
            email: EmailStr = Body(..., description="User's email address"),
            password: str = Body(..., description="User's password"),
        ):
            """Register a new user with the given email and password."""
            return await self.services["auth"].register(email, password)

        @self.router.post(
            "/users/verify-email",
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            tokens = client.users.verify_email(
                                email="jane.doe@example.com",
                                verification_code="1lklwal!awdclm"
                            )"""
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.verifyEmail({
                                    email: jane.doe@example.com",
                                    verificationCode: "1lklwal!awdclm"
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/users/login" \\
                                -H "Content-Type: application/x-www-form-urlencoded" \\
                                -d "email=jane.doe@example.com&verification_code=1lklwal!awdclm"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def verify_email(
            email: EmailStr = Body(..., description="User's email address"),
            verification_code: str = Body(
                ..., description="Email verification code"
            ),
        ) -> WrappedGenericMessageResponse:
            """Verify a user's email address."""
            result = await self.services["auth"].verify_email(
                email, verification_code
            )
            return GenericMessageResponse(message=result["message"])  # type: ignore

        @self.router.post(
            "/users/login",
            response_model=WrappedTokenResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            tokens = client.users.login(
                                email="jane.doe@example.com",
                                password="secure_password123"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.login({
                                    email: jane.doe@example.com",
                                    password: "secure_password123"
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/users/login" \\
                                -H "Content-Type: application/x-www-form-urlencoded" \\
                                -d "username=jane.doe@example.com&password=secure_password123"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def login(form_data: OAuth2PasswordRequestForm = Depends()):
            """Authenticate a user and provide access tokens."""
            return await self.services["auth"].login(
                form_data.username, form_data.password
            )

        @self.router.post(
            "/users/logout",
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # client.login(...)
                            result = client.users.logout()
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.logout();
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/users/logout" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def logout(
            token: str = Depends(oauth2_scheme),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGenericMessageResponse:
            """Log out the current user."""
            result = await self.services["auth"].logout(token)
            return GenericMessageResponse(message=result["message"])  # type: ignore

        @self.router.post(
            "/users/refresh-token",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # client.login(...)

                            new_tokens = client.users.refresh_token()
                            # New tokens are automatically stored in the client"""
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.refreshAccessToken();
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/users/refresh-token" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "refresh_token": "YOUR_REFRESH_TOKEN"
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def refresh_token(
            refresh_token: str = Body(..., description="Refresh token")
        ) -> WrappedTokenResponse:
            """Refresh the access token using a refresh token."""
            result = await self.services["auth"].refresh_access_token(
                refresh_token=refresh_token
            )
            return result

        @self.router.post(
            "/users/change-password",
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # client.login(...)

                            result = client.users.change_password(
                                current_password="old_password123",
                                new_password="new_secure_password456"
                            )"""
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.changePassword({
                                    currentPassword: "old_password123",
                                    newPassword: "new_secure_password456"
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/users/change-password" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "current_password": "old_password123",
                                    "new_password": "new_secure_password456"
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def change_password(
            current_password: str = Body(..., description="Current password"),
            new_password: str = Body(..., description="New password"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> GenericMessageResponse:
            """Change the authenticated user's password."""
            result = await self.services["auth"].change_password(
                auth_user, current_password, new_password
            )
            return GenericMessageResponse(message=result["message"])  # type: ignore

        @self.router.post(
            "/users/request-password-reset",
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            result = client.users.request_password_reset(
                                email="jane.doe@example.com"
                            )"""
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.requestPasswordReset({
                                    email: jane.doe@example.com",
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/users/request-password-reset" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "email": "jane.doe@example.com"
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def request_password_reset(
            email: EmailStr = Body(..., description="User's email address")
        ) -> WrappedGenericMessageResponse:
            """Request a password reset for a user."""
            result = await self.services["auth"].request_password_reset(email)
            return GenericMessageResponse(message=result["message"])  # type: ignore

        @self.router.post(
            "/users/reset-password",
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            result = client.users.reset_password(
                                reset_token="reset_token_received_via_email",
                                new_password="new_secure_password789"
                            )"""
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.resetPassword({
                                    resestToken: "reset_token_received_via_email",
                                    newPassword: "new_secure_password789"
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/users/reset-password" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "reset_token": "reset_token_received_via_email",
                                    "new_password": "new_secure_password789"
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def reset_password(
            reset_token: str = Body(..., description="Password reset token"),
            new_password: str = Body(..., description="New password"),
        ) -> WrappedGenericMessageResponse:
            """Reset a user's password using a reset token."""
            result = await self.services["auth"].confirm_password_reset(
                reset_token, new_password
            )
            return GenericMessageResponse(message=result["message"])  # type: ignore

        @self.router.get(
            "/users",
            summary="List Users",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # client.login(...)

                            # List users with filters
                            users = client.users.list(
                                offset=0,
                                limit=100,
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.list();
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r users list
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/users?offset=0&limit=100&username=john&email=john@example.com&is_active=true&is_superuser=false" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_users(
            # TODO - Implement the following parameters
            #     offset: int = Query(0, ge=0, example=0),
            #     limit: int = Query(100, ge=1, le=1000, example=100),
            #     username: Optional[str] = Query(None, example="john"),
            #     email: Optional[str] = Query(None, example="john@example.com"),
            #     is_active: Optional[bool] = Query(None, example=True),
            #     is_superuser: Optional[bool] = Query(None, example=False),
            #     auth_user=Depends(self.providers.auth.auth_wrapper),
            ids: list[str] = Query(
                [], description="List of user IDs to filter by"
            ),
            offset: int = Query(
                0,
                ge=0,
                description="Specifies the number of objects to skip. Defaults to 0.",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedUsersResponse:
            """
            List all users with pagination and filtering options.
            Only accessible by superusers.
            """

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `users_overview` endpoint.",
                    403,
                )

            user_uuids = [UUID(user_id) for user_id in ids]

            users_overview_response = await self.services[
                "management"
            ].users_overview(user_ids=user_uuids, offset=offset, limit=limit)
            return users_overview_response["results"], {  # type: ignore
                "total_entries": users_overview_response["total_entries"]
            }

        @self.router.get(
            "/users/me",
            summary="Get the Current User",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # client.login(...)

                            # Get user details
                            users = client.users.me()
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.retrieve();
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r users me
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/users/me" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_current_user(
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedUserResponse:
            """
            Get detailed information about the currently authenticated user.
            """
            return auth_user

        @self.router.get(
            "/users/{id}",
            summary="Get User Details",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # client.login(...)

                            # Get user details
                            users = client.users.retrieve(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.retrieve({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r users retrieve b4ac4dd6-5f27-596e-a55b-7cf242ca30aa
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_user(
            id: UUID = Path(
                ..., example="550e8400-e29b-41d4-a716-446655440000"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedUserResponse:
            """
            Get detailed information about a specific user.
            Users can only access their own information unless they are superusers.
            """
            if not auth_user.is_superuser and auth_user.id != id:
                raise R2RException(
                    "Only a superuser can call the get `user` endpoint for other users.",
                    403,
                )

            users_overview_response = await self.services[
                "management"
            ].users_overview(
                offset=0,
                limit=1,
                user_ids=[id],
            )

            return users_overview_response["results"][0]

        @self.router.delete(
            "/users/{id}",
            summary="Delete User",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                        from r2r import R2RClient

                        client = R2RClient("http://localhost:7272")
                        # client.login(...)

                        # Delete user
                        client.users.delete(id="550e8400-e29b-41d4-a716-446655440000", password="secure_password123")
                        """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                        const { r2rClient } = require("r2r-js");

                        const client = new r2rClient("http://localhost:7272");

                        function main() {
                            const response = await client.users.delete({
                                id: "550e8400-e29b-41d4-a716-446655440000",
                                password: "secure_password123"
                            });
                        }

                        main();
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_user(
            id: UUID = Path(
                ..., example="550e8400-e29b-41d4-a716-446655440000"
            ),
            password: Optional[str] = Body(
                None, description="User's current password"
            ),
            delete_vector_data: Optional[bool] = Body(
                False,
                description="Whether to delete the user's vector data",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Delete a specific user.
            Users can only delete their own account unless they are superusers.
            """
            if not auth_user.is_superuser and auth_user.id != id:
                raise R2RException(
                    "Only a superuser can delete other users.",
                    403,
                )

            await self.services["auth"].delete_user(
                user_id=id,
                password=password,
                delete_vector_data=delete_vector_data,
                is_superuser=auth_user.is_superuser,
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.get(
            "/users/{id}/collections",
            summary="Get User Collections",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # client.login(...)

                            # Get user collections
                            collections = client.user.list_collections(
                                "550e8400-e29b-41d4-a716-446655440000",
                                offset=0,
                                limit=100
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.listCollections({
                                    id: "550e8400-e29b-41d4-a716-446655440000",
                                    offset: 0,
                                    limit: 100
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r users list-collections 550e8400-e29b-41d4-a716-446655440000
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/collections?offset=0&limit=100" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_user_collections(
            id: UUID = Path(
                ..., example="550e8400-e29b-41d4-a716-446655440000"
            ),
            offset: int = Query(
                0,
                ge=0,
                description="Specifies the number of objects to skip. Defaults to 0.",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCollectionsResponse:
            """
            Get all collections associated with a specific user.
            Users can only access their own collections unless they are superusers.
            """
            if auth_user.id != id and not auth_user.is_superuser:
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )
            user_collection_response = await self.services[
                "management"
            ].collections_overview(
                offset=offset,
                limit=limit,
                user_ids=[id],
            )
            return user_collection_response["results"], {  # type: ignore
                "total_entries": user_collection_response["total_entries"]
            }

        @self.router.post(
            "/users/{id}/collections/{collection_id}",
            summary="Add User to Collection",
            response_model=WrappedBooleanResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # client.login(...)

                            # Add user to collection
                            client.users.add_to_collection(
                                id="550e8400-e29b-41d4-a716-446655440000",
                                collection_id="750e8400-e29b-41d4-a716-446655440000"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.addToCollection({
                                    id: "550e8400-e29b-41d4-a716-446655440000",
                                    collectionId: "750e8400-e29b-41d4-a716-446655440000"
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r users add-to-collection 550e8400-e29b-41d4-a716-446655440000 750e8400-e29b-41d4-a716-446655440000
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/collections/750e8400-e29b-41d4-a716-446655440000" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def add_user_to_collection(
            id: UUID = Path(
                ..., example="550e8400-e29b-41d4-a716-446655440000"
            ),
            collection_id: UUID = Path(
                ..., example="750e8400-e29b-41d4-a716-446655440000"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            if auth_user.id != id and not auth_user.is_superuser:
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            # TODO - Do we need a check on user access to the collection?
            await self.services["management"].add_user_to_collection(  # type: ignore
                id, collection_id
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.delete(
            "/users/{id}/collections/{collection_id}",
            summary="Remove User from Collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # client.login(...)

                            # Remove user from collection
                            client.users.remove_from_collection(
                                id="550e8400-e29b-41d4-a716-446655440000",
                                collection_id="750e8400-e29b-41d4-a716-446655440000"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.removeFromCollection({
                                    id: "550e8400-e29b-41d4-a716-446655440000",
                                    collectionId: "750e8400-e29b-41d4-a716-446655440000"
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r users remove-from-collection 550e8400-e29b-41d4-a716-446655440000 750e8400-e29b-41d4-a716-446655440000
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/collections/750e8400-e29b-41d4-a716-446655440000" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def remove_user_from_collection(
            id: UUID = Path(
                ..., example="550e8400-e29b-41d4-a716-446655440000"
            ),
            collection_id: UUID = Path(
                ..., example="750e8400-e29b-41d4-a716-446655440000"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Remove a user from a collection.
            Requires either superuser status or access to the collection.
            """
            if auth_user.id != id and not auth_user.is_superuser:
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            # TODO - Do we need a check on user access to the collection?
            await self.services["management"].remove_user_from_collection(  # type: ignore
                id, collection_id
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/users/{id}",
            summary="Update User",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # client.login(...)

                            # Update user
                            updated_user = client.update_user(
                                "550e8400-e29b-41d4-a716-446655440000",
                                name="John Doe"
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.users.update({
                                    id: "550e8400-e29b-41d4-a716-446655440000",
                                    name: "John Doe"
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "id": "550e8400-e29b-41d4-a716-446655440000",
                                    "name": "John Doe",
                                }'
                            """
                        ),
                    },
                ]
            },
        )
        # TODO - Modify update user to have synced params with user object
        @self.base_endpoint
        async def update_user(
            id: UUID = Path(..., description="ID of the user to update"),
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedUserResponse:
            """
            Update user information.
            Users can only update their own information unless they are superusers.
            Superuser status can only be modified by existing superusers.
            """

            if is_superuser is not None and not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can update the superuser status of a user",
                    403,
                )
            if not auth_user.is_superuser and auth_user.id != id:
                raise R2RException(
                    "Only superusers can update other users' information",
                    403,
                )

            return await self.services["auth"].update_user(
                user_id=id,
                email=email,
                is_superuser=is_superuser,
                name=name,
                bio=bio,
                profile_picture=profile_picture,
            )
