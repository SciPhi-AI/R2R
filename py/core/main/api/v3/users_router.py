import logging
import textwrap
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field

from core.base import R2RException
from core.base.api.models import (
    CollectionResponse,
    GenericMessageResponse,
    PaginatedResultsWrapper,
    ResultsWrapper,
    UserOverviewResponse,
    WrappedCollectionResponse,
    WrappedGenericMessageResponse,
    WrappedTokenResponse,
    WrappedUserOverviewResponse,
    WrappedUserResponse,
)

from .base_router import BaseRouterV3


class UserResponse(BaseModel):
    """Detailed user information response"""

    id: UUID = Field(
        ...,
        description="Unique identifier for the user",
    )
    username: str = Field(
        ...,
        description="User's login username",
    )
    email: str = Field(
        ...,
        description="User's email address",
    )
    is_active: bool = Field(
        ...,
        description="Whether the user account is currently active",
    )
    is_superuser: bool = Field(
        ...,
        description="Whether the user has superuser privileges",
    )
    created_at: str = Field(
        ...,
        description="ISO formatted timestamp of when the user was created",
    )
    updated_at: str = Field(
        ...,
        description="ISO formatted timestamp of when the user was last updated",
    )
    last_login: Optional[str] = Field(
        None,
        description="ISO formatted timestamp of user's last login",
    )
    collection_ids: list[UUID] = Field(
        ...,
        description="List of collection IDs the user has access to",
    )
    metadata: Optional[dict] = Field(
        None,
        description="Additional user metadata stored as key-value pairs",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "john.doe",
                "email": "john.doe@example.com",
                "is_active": True,
                "is_superuser": False,
                "created_at": "2024-03-15T14:30:00Z",
                "updated_at": "2024-03-20T09:15:00Z",
                "last_login": "2024-03-22T16:45:00Z",
                "collection_ids": [
                    "750e8400-e29b-41d4-a716-446655440000",
                    "850e8400-e29b-41d4-a716-446655440000",
                ],
                "metadata": {
                    "department": "Engineering",
                    "title": "Senior Developer",
                    "location": "New York",
                },
            }
        }


class UserActivityResponse(BaseModel):
    """User activity statistics"""

    total_documents: int = Field(
        ...,
        description="Total number of documents owned by the user",
    )
    total_collections: int = Field(
        ...,
        description="Total number of collections the user has access to",
    )
    last_activity: Optional[str] = Field(
        None,
        description="ISO formatted timestamp of the user's last activity",
    )
    recent_collections: list[UUID] = Field(
        ...,
        description="List of recently accessed collection IDs",
    )
    recent_documents: list[UUID] = Field(
        ...,
        description="List of recently accessed document IDs",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total_documents": 156,
                "total_collections": 8,
                "last_activity": "2024-03-22T16:45:00Z",
                "recent_collections": [
                    "750e8400-e29b-41d4-a716-446655440000",
                    "850e8400-e29b-41d4-a716-446655440000",
                ],
                "recent_documents": [
                    "950e8400-e29b-41d4-a716-446655440000",
                    "a50e8400-e29b-41d4-a716-446655440000",
                ],
            }
        }


logger = logging.getLogger()
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
        ):
            """Verify a user's email address."""
            result = await self.services["auth"].verify_email(
                email, verification_code
            )
            return GenericMessageResponse(message=result["message"])

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
                            )"""
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
                            result = client.users.logout()"""
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
        ):
            """Log out the current user."""
            result = await self.services["auth"].logout(token)
            return GenericMessageResponse(message=result["message"])

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
        ):
            """Change the authenticated user's password."""
            result = await self.services["auth"].change_password(
                auth_user, current_password, new_password
            )
            return GenericMessageResponse(message=result["message"])

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
        ):
            """Request a password reset for a user."""
            result = await self.services["auth"].request_password_reset(email)
            return GenericMessageResponse(message=result["message"])

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
        ):
            """Reset a user's password using a reset token."""
            result = await self.services["auth"].confirm_password_reset(
                reset_token, new_password
            )
            return GenericMessageResponse(message=result["message"])

        @self.router.get(
            "/users",
            summary="List Users",
            response_model=WrappedUserOverviewResponse,
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
            # TODO - Implement the following parameters
            #     offset: int = Query(0, ge=0, example=0),
            #     limit: int = Query(100, ge=1, le=1000, example=100),
            #     username: Optional[str] = Query(None, example="john"),
            #     email: Optional[str] = Query(None, example="john@example.com"),
            #     is_active: Optional[bool] = Query(None, example=True),
            #     is_superuser: Optional[bool] = Query(None, example=False),
            #     auth_user=Depends(self.providers.auth.auth_wrapper),
            # ) -> PaginatedResultsWrapper[List[UserOverviewResponse]]:
            user_ids: Optional[list[UUID]] = Query(
                None, description="List of user IDs to filter by"
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
        ):  #  -> WrappedUserOverviewResponse:
            """
            List all users with pagination and filtering options.
            Only accessible by superusers.
            """

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `users_overview` endpoint.",
                    403,
                )

            users_overview_response = await self.services[
                "management"
            ].users_overview(user_ids=user_ids, offset=offset, limit=limit)
            return users_overview_response["results"], {  # type: ignore
                "total_entries": users_overview_response["total_entries"]
            }

        @self.router.get(
            "/users/{id}",
            summary="Get User Details",
            # response_model=ResultsWrapper[UserOverviewResponse],
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
        ) -> ResultsWrapper[UserOverviewResponse]:
            """
            Get detailed information about a specific user.
            Users can only access their own information unless they are superusers.
            """
            if not auth_user.is_superuser and not auth_user.id == id:
                raise R2RException(
                    "Only a superuser can call the get `user` endpoint for other users.",
                    403,
                )

            user_overview_response = await self.services[
                "management"
            ].users_overview([id])
            if len(user_overview_response["results"]) == 0:
                raise R2RException("User not found.", 404)
            return user_overview_response["results"][0].dict(), {  # type: ignore
                "total_entries": user_overview_response["total_entries"]
            }

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
                            collections = client.get_user_collections(
                                "550e8400-e29b-41d4-a716-446655440000",
                                offset=0,
                                limit=100
                            )
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
        ) -> PaginatedResultsWrapper[list[CollectionResponse]]:
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
            ].get_collections_overview(
                offset=offset,
                limit=limit,
                filter_user_ids=[id],
            )
            return user_collection_response["results"], {  # type: ignore
                "total_entries": user_collection_response["total_entries"]
            }

        @self.router.post(
            "/users/{id}/collections/{collection_id}",
            summary="Add User to Collection",
            response_model=ResultsWrapper[bool],
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
                            client.users.add_user_to_collection(
                                id="550e8400-e29b-41d4-a716-446655440000",
                                collection_id="750e8400-e29b-41d4-a716-446655440000"
                            )
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
        ) -> ResultsWrapper[bool]:
            if auth_user.id != id and not auth_user.is_superuser:
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            # TODO - Do we need a check on user access to the collection?
            # TODO - Do we need a check on user access to the collection?
            await self.services["management"].add_user_to_collection(  # type: ignore
                id, collection_id
            )
            return True  # type: ignore

        @self.router.post(
            "/users/{id}/collections/{collection_id}",
            summary="Remove User from Collection",
            response_model=ResultsWrapper[None],
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
                            client.remove_user_from_collection(
                                id="550e8400-e29b-41d4-a716-446655440000",
                                collection_id="750e8400-e29b-41d4-a716-446655440000"
                            )
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
        ) -> ResultsWrapper[bool]:
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
            # TODO - Do we need a check on user access to the collection?
            await self.services["management"].remove_user_from_collection(  # type: ignore
                id, collection_id
            )
            return True  # type: ignore

        @self.router.post(
            "/users/{id}",
            summary="Update User",
            # response_model=ResultsWrapper[UserResponse],
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
            if not auth_user.is_superuser:
                if not auth_user.id == id:
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
