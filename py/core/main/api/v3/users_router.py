import logging
import os
import textwrap
import urllib.parse
from typing import Optional
from uuid import UUID

import requests
from fastapi import Body, Depends, HTTPException, Path, Query
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import EmailStr

from core.base import R2RException
from core.base.api.models import (
    GenericBooleanResponse,
    GenericMessageResponse,
    WrappedAPIKeyResponse,
    WrappedAPIKeysResponse,
    WrappedBooleanResponse,
    WrappedCollectionsResponse,
    WrappedGenericMessageResponse,
    WrappedLimitsResponse,
    WrappedLoginResponse,
    WrappedTokenResponse,
    WrappedUserResponse,
    WrappedUsersResponse,
)

from ...abstractions import R2RProviders, R2RServices
from ...config import R2RConfig
from .base_router import BaseRouterV3

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class UsersRouter(BaseRouterV3):
    def __init__(
        self, providers: R2RProviders, services: R2RServices, config: R2RConfig
    ):
        logging.info("Initializing UsersRouter")
        super().__init__(providers, services, config)
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI")

        self.github_client_id = os.environ.get("GITHUB_CLIENT_ID")
        self.github_client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
        self.github_redirect_uri = os.environ.get("GITHUB_REDIRECT_URI")

    def _setup_routes(self):
        @self.router.post(
            "/users",
            # dependencies=[Depends(self.rate_limit_dependency)],
            response_model=WrappedUserResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            new_user = client.users.create(
                                email="jane.doe@example.com",
                                password="secure_password123"
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.create({
                                    email: "jane.doe@example.com",
                                    password: "secure_password123"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/users" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "email": "jane.doe@example.com",
                                    "password": "secure_password123"
                                }'"""),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def register(
            email: EmailStr = Body(..., description="User's email address"),
            password: str = Body(..., description="User's password"),
            name: str | None = Body(
                None, description="The name for the new user"
            ),
            bio: str | None = Body(
                None, description="The bio for the new user"
            ),
            profile_picture: str | None = Body(
                None, description="Updated user profile picture"
            ),
            # auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedUserResponse:
            """Register a new user with the given email and password."""

            # TODO: Do we really want this validation? The default password for the superuser would not pass...
            def validate_password(password: str) -> bool:
                if len(password) < 10:
                    return False
                if not any(c.isupper() for c in password):
                    return False
                if not any(c.islower() for c in password):
                    return False
                if not any(c.isdigit() for c in password):
                    return False
                if not any(c in "!@#$%^&*" for c in password):
                    return False
                return True

            # if not validate_password(password):
            #     raise R2RException(
            #         f"Password must be at least 10 characters long and contain at least one uppercase letter, one lowercase letter, one digit, and one special character from '!@#$%^&*'.",
            #         400,
            #     )

            registration_response = await self.services.auth.register(
                email=email,
                password=password,
                name=name,
                bio=bio,
                profile_picture=profile_picture,
            )

            return registration_response  # type: ignore

        @self.router.post(
            "/users/export",
            summary="Export users to CSV",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            response = client.users.export(
                                output_path="export.csv",
                                columns=["id", "name", "created_at"],
                                include_header=True,
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                await client.users.export({
                                    outputPath: "export.csv",
                                    columns: ["id", "name", "created_at"],
                                    includeHeader: true,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "http://127.0.0.1:7272/v3/users/export" \
                            -H "Authorization: Bearer YOUR_API_KEY" \
                            -H "Content-Type: application/json" \
                            -H "Accept: text/csv" \
                            -d '{ "columns": ["id", "name", "created_at"], "include_header": true }' \
                            --output export.csv
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def export_users(
            background_tasks: BackgroundTasks,
            columns: Optional[list[str]] = Body(
                None, description="Specific columns to export"
            ),
            filters: Optional[dict] = Body(
                None, description="Filters to apply to the export"
            ),
            include_header: Optional[bool] = Body(
                True, description="Whether to include column headers"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> FileResponse:
            """Export users as a CSV file."""

            if not auth_user.is_superuser:
                raise R2RException(
                    status_code=403,
                    message="Only a superuser can export data.",
                )

            (
                csv_file_path,
                temp_file,
            ) = await self.services.management.export_users(
                columns=columns,
                filters=filters,
                include_header=include_header
                if include_header is not None
                else True,
            )

            background_tasks.add_task(temp_file.close)

            return FileResponse(
                path=csv_file_path,
                media_type="text/csv",
                filename="users_export.csv",
            )

        @self.router.post(
            "/users/verify-email",
            # dependencies=[Depends(self.rate_limit_dependency)],
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            tokens = client.users.verify_email(
                                email="jane.doe@example.com",
                                verification_code="1lklwal!awdclm"
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.verifyEmail({
                                    email: jane.doe@example.com",
                                    verificationCode: "1lklwal!awdclm"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/users/login" \\
                                -H "Content-Type: application/x-www-form-urlencoded" \\
                                -d "email=jane.doe@example.com&verification_code=1lklwal!awdclm"
                            """),
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
            user = (
                await self.providers.database.users_handler.get_user_by_email(
                    email
                )
            )
            if user and user.is_verified:
                raise R2RException(
                    status_code=400,
                    message="This email is already verified. Please log in.",
                )

            result = await self.services.auth.verify_email(
                email, verification_code
            )
            return GenericMessageResponse(message=result["message"])  # type: ignore

        @self.router.post(
            "/users/send-verification-email",
            dependencies=[
                Depends(self.providers.auth.auth_wrapper(public=True))
            ],
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            tokens = client.users.send_verification_email(
                                email="jane.doe@example.com",
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.sendVerificationEmail({
                                    email: jane.doe@example.com",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/users/send-verification-email" \\
                                -H "Content-Type: application/x-www-form-urlencoded" \\
                                -d "email=jane.doe@example.com"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def send_verification_email(
            email: EmailStr = Body(..., description="User's email address"),
        ) -> WrappedGenericMessageResponse:
            """Send a user's email a verification code."""
            user = (
                await self.providers.database.users_handler.get_user_by_email(
                    email
                )
            )
            if user and user.is_verified:
                raise R2RException(
                    status_code=400,
                    message="This email is already verified. Please log in.",
                )

            await self.services.auth.send_verification_email(email=email)
            return GenericMessageResponse(
                message="A verification email has been sent."
            )  # type: ignore

        @self.router.post(
            "/users/login",
            # dependencies=[Depends(self.rate_limit_dependency)],
            response_model=WrappedTokenResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            tokens = client.users.login(
                                email="jane.doe@example.com",
                                password="secure_password123"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.login({
                                    email: jane.doe@example.com",
                                    password: "secure_password123"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/users/login" \\
                                -H "Content-Type: application/x-www-form-urlencoded" \\
                                -d "username=jane.doe@example.com&password=secure_password123"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def login(
            form_data: OAuth2PasswordRequestForm = Depends(),
        ) -> WrappedLoginResponse:
            """Authenticate a user and provide access tokens."""
            return await self.services.auth.login(  # type: ignore
                form_data.username, form_data.password
            )

        @self.router.post(
            "/users/logout",
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)
                            result = client.users.logout()
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.logout();
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/users/logout" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def logout(
            token: str = Depends(oauth2_scheme),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGenericMessageResponse:
            """Log out the current user."""
            result = await self.services.auth.logout(token)
            return GenericMessageResponse(message=result["message"])  # type: ignore

        @self.router.post(
            "/users/refresh-token",
            # dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            new_tokens = client.users.refresh_token()
                            # New tokens are automatically stored in the client"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.refreshAccessToken();
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/users/refresh-token" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "refresh_token": "YOUR_REFRESH_TOKEN"
                                }'"""),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def refresh_token(
            refresh_token: str = Body(..., description="Refresh token"),
        ) -> WrappedTokenResponse:
            """Refresh the access token using a refresh token."""
            result = await self.services.auth.refresh_access_token(
                refresh_token=refresh_token
            )
            return result  # type: ignore

        @self.router.post(
            "/users/change-password",
            dependencies=[Depends(self.rate_limit_dependency)],
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            result = client.users.change_password(
                                current_password="old_password123",
                                new_password="new_secure_password456"
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.changePassword({
                                    currentPassword: "old_password123",
                                    newPassword: "new_secure_password456"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/users/change-password" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "current_password": "old_password123",
                                    "new_password": "new_secure_password456"
                                }'"""),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def change_password(
            current_password: str = Body(..., description="Current password"),
            new_password: str = Body(..., description="New password"),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGenericMessageResponse:
            """Change the authenticated user's password."""
            result = await self.services.auth.change_password(
                auth_user, current_password, new_password
            )
            return GenericMessageResponse(message=result["message"])  # type: ignore

        @self.router.post(
            "/users/request-password-reset",
            dependencies=[
                Depends(self.providers.auth.auth_wrapper(public=True))
            ],
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            result = client.users.request_password_reset(
                                email="jane.doe@example.com"
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.requestPasswordReset({
                                    email: jane.doe@example.com",
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/users/request-password-reset" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "email": "jane.doe@example.com"
                                }'"""),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def request_password_reset(
            email: EmailStr = Body(..., description="User's email address"),
        ) -> WrappedGenericMessageResponse:
            """Request a password reset for a user."""
            result = await self.services.auth.request_password_reset(email)
            return GenericMessageResponse(message=result["message"])  # type: ignore

        @self.router.post(
            "/users/reset-password",
            dependencies=[
                Depends(self.providers.auth.auth_wrapper(public=True))
            ],
            response_model=WrappedGenericMessageResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            result = client.users.reset_password(
                                reset_token="reset_token_received_via_email",
                                new_password="new_secure_password789"
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.resetPassword({
                                    resestToken: "reset_token_received_via_email",
                                    newPassword: "new_secure_password789"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/users/reset-password" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "reset_token": "reset_token_received_via_email",
                                    "new_password": "new_secure_password789"
                                }'"""),
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
            result = await self.services.auth.confirm_password_reset(
                reset_token, new_password
            )
            return GenericMessageResponse(message=result["message"])  # type: ignore

        @self.router.get(
            "/users",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="List Users",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            # List users with filters
                            users = client.users.list(
                                offset=0,
                                limit=100,
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.list();
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/users?offset=0&limit=100&username=john&email=john@example.com&is_active=true&is_superuser=false" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_users(
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedUsersResponse:
            """List all users with pagination and filtering options.

            Only accessible by superusers.
            """

            if not auth_user.is_superuser:
                raise R2RException(
                    status_code=403,
                    message="Only a superuser can call the `users_overview` endpoint.",
                )

            user_uuids = [UUID(user_id) for user_id in ids]

            users_overview_response = (
                await self.services.management.users_overview(
                    user_ids=user_uuids, offset=offset, limit=limit
                )
            )
            return users_overview_response["results"], {  # type: ignore
                "total_entries": users_overview_response["total_entries"]
            }

        @self.router.get(
            "/users/me",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Get the Current User",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            # Get user details
                            users = client.users.me()
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.retrieve();
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/users/me" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_current_user(
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedUserResponse:
            """Get detailed information about the currently authenticated
            user."""
            return auth_user

        @self.router.get(
            "/users/{id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Get User Details",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            # Get user details
                            users = client.users.retrieve(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.retrieve({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_user(
            id: UUID = Path(
                ..., example="550e8400-e29b-41d4-a716-446655440000"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedUserResponse:
            """Get detailed information about a specific user.

            Users can only access their own information unless they are
            superusers.
            """
            if not auth_user.is_superuser and auth_user.id != id:
                raise R2RException(
                    "Only a superuser can call the get `user` endpoint for other users.",
                    403,
                )

            users_overview_response = (
                await self.services.management.users_overview(
                    offset=0,
                    limit=1,
                    user_ids=[id],
                )
            )

            return users_overview_response["results"][0]

        @self.router.delete(
            "/users/{id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Delete User",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                        from r2r import R2RClient

                        client = R2RClient()
                        # client.login(...)

                        # Delete user
                        client.users.delete(id="550e8400-e29b-41d4-a716-446655440000", password="secure_password123")
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                        const { r2rClient } = require("r2r-js");

                        const client = new r2rClient();

                        function main() {
                            const response = await client.users.delete({
                                id: "550e8400-e29b-41d4-a716-446655440000",
                                password: "secure_password123"
                            });
                        }

                        main();
                        """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Delete a specific user.

            Users can only delete their own account unless they are superusers.
            """
            if not auth_user.is_superuser and auth_user.id != id:
                raise R2RException(
                    "Only a superuser can delete other users.",
                    403,
                )

            await self.services.auth.delete_user(
                user_id=id,
                password=password,
                delete_vector_data=delete_vector_data or False,
                is_superuser=auth_user.is_superuser,
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.get(
            "/users/{id}/collections",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Get User Collections",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            # Get user collections
                            collections = client.user.list_collections(
                                "550e8400-e29b-41d4-a716-446655440000",
                                offset=0,
                                limit=100
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.listCollections({
                                    id: "550e8400-e29b-41d4-a716-446655440000",
                                    offset: 0,
                                    limit: 100
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/collections?offset=0&limit=100" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedCollectionsResponse:
            """Get all collections associated with a specific user.

            Users can only access their own collections unless they are
            superusers.
            """
            if auth_user.id != id and not auth_user.is_superuser:
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )
            user_collection_response = (
                await self.services.management.collections_overview(
                    offset=offset,
                    limit=limit,
                    user_ids=[id],
                )
            )
            return user_collection_response["results"], {  # type: ignore
                "total_entries": user_collection_response["total_entries"]
            }

        @self.router.post(
            "/users/{id}/collections/{collection_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Add User to Collection",
            response_model=WrappedBooleanResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            # Add user to collection
                            client.users.add_to_collection(
                                id="550e8400-e29b-41d4-a716-446655440000",
                                collection_id="750e8400-e29b-41d4-a716-446655440000"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.addToCollection({
                                    id: "550e8400-e29b-41d4-a716-446655440000",
                                    collectionId: "750e8400-e29b-41d4-a716-446655440000"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/collections/750e8400-e29b-41d4-a716-446655440000" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            if auth_user.id != id and not auth_user.is_superuser:
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            # TODO - Do we need a check on user access to the collection?
            await self.services.management.add_user_to_collection(  # type: ignore
                id, collection_id
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.delete(
            "/users/{id}/collections/{collection_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Remove User from Collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            # Remove user from collection
                            client.users.remove_from_collection(
                                id="550e8400-e29b-41d4-a716-446655440000",
                                collection_id="750e8400-e29b-41d4-a716-446655440000"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.removeFromCollection({
                                    id: "550e8400-e29b-41d4-a716-446655440000",
                                    collectionId: "750e8400-e29b-41d4-a716-446655440000"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            curl -X DELETE "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/collections/750e8400-e29b-41d4-a716-446655440000" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Remove a user from a collection.

            Requires either superuser status or access to the collection.
            """
            if auth_user.id != id and not auth_user.is_superuser:
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            # TODO - Do we need a check on user access to the collection?
            await self.services.management.remove_user_from_collection(  # type: ignore
                id, collection_id
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/users/{id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Update User",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            # Update user
                            updated_user = client.update_user(
                                "550e8400-e29b-41d4-a716-446655440000",
                                name="John Doe"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.users.update({
                                    id: "550e8400-e29b-41d4-a716-446655440000",
                                    name: "John Doe"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json" \\
                                -d '{
                                    "id": "550e8400-e29b-41d4-a716-446655440000",
                                    "name": "John Doe",
                                }'
                            """),
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
            limits_overrides: dict = Body(
                None,
                description="Updated limits overrides",
            ),
            metadata: dict[str, str | None] | None = None,
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedUserResponse:
            """Update user information.

            Users can only update their own information unless they are
            superusers. Superuser status can only be modified by existing
            superusers.
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

            if not auth_user.is_superuser and limits_overrides is not None:
                raise R2RException(
                    "Only superusers can update other users' limits overrides",
                    403,
                )

            # Pass `metadata` to our auth or management service so it can do a
            # partial (Stripe-like) merge of metadata.
            return await self.services.auth.update_user(  # type: ignore
                user_id=id,
                email=email,
                is_superuser=is_superuser,
                name=name,
                bio=bio,
                profile_picture=profile_picture,
                limits_overrides=limits_overrides,
                new_metadata=metadata,
            )

        @self.router.post(
            "/users/{id}/api-keys",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Create User API Key",
            response_model=WrappedAPIKeyResponse,
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            result = client.users.create_api_key(
                                id="550e8400-e29b-41d4-a716-446655440000",
                                name="My API Key",
                                description="API key for accessing the app",
                            )
                            # result["api_key"] contains the newly created API key
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/api-keys" \\
                                -H "Authorization: Bearer YOUR_API_TOKEN" \\
                                -d '{"name": "My API Key", "description": "API key for accessing the app"}'
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_user_api_key(
            id: UUID = Path(
                ..., description="ID of the user for whom to create an API key"
            ),
            name: Optional[str] = Body(
                None, description="Name of the API key"
            ),
            description: Optional[str] = Body(
                None, description="Description of the API key"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedAPIKeyResponse:
            """Create a new API key for the specified user.

            Only superusers or the user themselves may create an API key.
            """
            if auth_user.id != id and not auth_user.is_superuser:
                raise R2RException(
                    "Only the user themselves or a superuser can create API keys for this user.",
                    403,
                )

            api_key = await self.services.auth.create_user_api_key(
                id, name=name, description=description
            )
            return api_key  # type: ignore

        @self.router.get(
            "/users/{id}/api-keys",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="List User API Keys",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            keys = client.users.list_api_keys(
                                id="550e8400-e29b-41d4-a716-446655440000"
                            )
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/api-keys" \\
                                -H "Authorization: Bearer YOUR_API_TOKEN"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_user_api_keys(
            id: UUID = Path(
                ..., description="ID of the user whose API keys to list"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedAPIKeysResponse:
            """List all API keys for the specified user.

            Only superusers or the user themselves may list the API keys.
            """
            if auth_user.id != id and not auth_user.is_superuser:
                raise R2RException(
                    "Only the user themselves or a superuser can list API keys for this user.",
                    403,
                )

            keys = (
                await self.providers.database.users_handler.get_user_api_keys(
                    id
                )
            )
            return keys, {"total_entries": len(keys)}  # type: ignore

        @self.router.delete(
            "/users/{id}/api-keys/{key_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Delete User API Key",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient
                            from uuid import UUID

                            client = R2RClient()
                            # client.login(...)

                            response = client.users.delete_api_key(
                                id="550e8400-e29b-41d4-a716-446655440000",
                                key_id="d9c562d4-3aef-43e8-8f08-0cf7cd5e0a25"
                            )
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X DELETE "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/api-keys/d9c562d4-3aef-43e8-8f08-0cf7cd5e0a25" \\
                                -H "Authorization: Bearer YOUR_API_TOKEN"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_user_api_key(
            id: UUID = Path(..., description="ID of the user"),
            key_id: UUID = Path(
                ..., description="ID of the API key to delete"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Delete a specific API key for the specified user.

            Only superusers or the user themselves may delete the API key.
            """
            if auth_user.id != id and not auth_user.is_superuser:
                raise R2RException(
                    "Only the user themselves or a superuser can delete this API key.",
                    403,
                )

            success = (
                await self.providers.database.users_handler.delete_api_key(
                    id, key_id
                )
            )
            if not success:
                raise R2RException(
                    "API key not found or could not be deleted", 400
                )
            return {"success": True}  # type: ignore

        @self.router.get(
            "/users/{id}/limits",
            summary="Fetch User Limits",
            responses={
                200: {
                    "description": "Returns system default limits, user overrides, and final effective settings."
                },
                403: {
                    "description": "If the requesting user is neither the same user nor a superuser."
                },
                404: {"description": "If the user ID does not exist."},
            },
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
                            from r2r import R2RClient

                            client = R2RClient()
                            # client.login(...)

                            user_limits = client.users.get_limits("550e8400-e29b-41d4-a716-446655440000")
                        """,
                    },
                    {
                        "lang": "JavaScript",
                        "source": """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();
                            // await client.users.login(...)

                            async function main() {
                                const userLimits = await client.users.getLimits({
                                    id: "550e8400-e29b-41d4-a716-446655440000"
                                });
                                console.log(userLimits);
                            }

                            main();
                        """,
                    },
                    {
                        "lang": "cURL",
                        "source": """
                            curl -X GET "https://api.example.com/v3/users/550e8400-e29b-41d4-a716-446655440000/limits" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                        """,
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_user_limits(
            id: UUID = Path(
                ..., description="ID of the user to fetch limits for"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedLimitsResponse:
            """Return the system default limits, user-level overrides, and
            final "effective" limit settings for the specified user.

            Only superusers or the user themself may fetch these values.
            """
            if (auth_user.id != id) and (not auth_user.is_superuser):
                raise R2RException(
                    "Only the user themselves or a superuser can view these limits.",
                    status_code=403,
                )

            # This calls the new helper you created in ManagementService
            limits_info = await self.services.management.get_all_user_limits(
                id
            )
            return limits_info  # type: ignore

        @self.router.get("/users/oauth/google/authorize")
        @self.base_endpoint
        async def google_authorize() -> WrappedGenericMessageResponse:
            """Redirect user to Google's OAuth 2.0 consent screen."""
            state = "some_random_string_or_csrf_token"  # Usually you store a random state in session/Redis
            scope = "openid email profile"

            # Build the Google OAuth URL
            params = {
                "client_id": self.google_client_id,
                "redirect_uri": self.google_redirect_uri,
                "response_type": "code",
                "scope": scope,
                "state": state,
                "access_type": "offline",  # to get refresh token if needed
                "prompt": "consent",  # Force consent each time if you want
            }
            google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
            return GenericMessageResponse(message=google_auth_url)  # type: ignore

        @self.router.get("/users/oauth/google/callback")
        @self.base_endpoint
        async def google_callback(
            code: str = Query(...), state: str = Query(...)
        ) -> WrappedLoginResponse:
            """Google's callback that will receive the `code` and `state`.

            We then exchange code for tokens, verify, and log the user in.
            """
            # 1. Exchange `code` for tokens
            token_data = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": self.google_client_id,
                    "client_secret": self.google_client_secret,
                    "redirect_uri": self.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            ).json()
            if "error" in token_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to get token: {token_data}",
                )

            # 2. Verify the ID token
            id_token_str = token_data["id_token"]
            try:
                # google_auth.transport.requests.Request() is a session for verifying
                id_info = id_token.verify_oauth2_token(
                    id_token_str,
                    google_requests.Request(),
                    self.google_client_id,
                )
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Token verification failed: {str(e)}",
                ) from e

            # id_info will contain "sub", "email", etc.
            google_id = id_info["sub"]
            email = id_info.get("email")
            email = email or f"{google_id}@google_oauth.fake"

            # 3. Now call our R2RAuthProvider method that handles "oauth-based" user creation or login
            return await self.providers.auth.oauth_callback_handler(  # type: ignore
                provider="google",
                oauth_id=google_id,
                email=email,
            )

        @self.router.get("/users/oauth/github/authorize")
        @self.base_endpoint
        async def github_authorize() -> WrappedGenericMessageResponse:
            """Redirect user to GitHub's OAuth consent screen."""
            state = "some_random_string_or_csrf_token"
            scope = "read:user user:email"

            params = {
                "client_id": self.github_client_id,
                "redirect_uri": self.github_redirect_uri,
                "scope": scope,
                "state": state,
            }
            github_auth_url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
            return GenericMessageResponse(message=github_auth_url)  # type: ignore

        @self.router.get("/users/oauth/github/callback")
        @self.base_endpoint
        async def github_callback(
            code: str = Query(...), state: str = Query(...)
        ) -> WrappedLoginResponse:
            """GitHub callback route to exchange code for an access_token, then
            fetch user info from GitHub's API, then do the same 'oauth-based'
            login or registration."""
            # 1. Exchange code for access_token
            token_resp = requests.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": self.github_client_id,
                    "client_secret": self.github_client_secret,
                    "code": code,
                    "redirect_uri": self.github_redirect_uri,
                    "state": state,
                },
                headers={"Accept": "application/json"},
            )
            token_data = token_resp.json()
            if "error" in token_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to get token: {token_data}",
                )
            access_token = token_data["access_token"]

            # 2. Use the access_token to fetch user info
            user_info_resp = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}"},
            ).json()

            github_id = str(
                user_info_resp["id"]
            )  # GitHub user ID is typically an integer
            # fetch email (sometimes you need to call /user/emails endpoint if user sets email private)
            email = user_info_resp.get("email")
            email = email or f"{github_id}@github_oauth.fake"
            # 3. Pass to your auth provider
            return await self.providers.auth.oauth_callback_handler(  # type: ignore
                provider="github",
                oauth_id=github_id,
                email=email,
            )
