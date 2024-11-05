import datetime
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel, Field, Json

from core.base import R2RException
from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper

from .base_router import BaseRouterV3


class UserResponse(BaseModel):
    """Detailed user information response"""

    id: UUID = Field(
        ...,
        description="Unique identifier for the user",
        example="550e8400-e29b-41d4-a716-446655440000",
    )
    username: str = Field(
        ..., description="User's login username", example="john.doe"
    )
    email: str = Field(
        ..., description="User's email address", example="john.doe@example.com"
    )
    is_active: bool = Field(
        ...,
        description="Whether the user account is currently active",
        example=True,
    )
    is_superuser: bool = Field(
        ...,
        description="Whether the user has superuser privileges",
        example=False,
    )
    created_at: str = Field(
        ...,
        description="ISO formatted timestamp of when the user was created",
        example="2024-03-15T14:30:00Z",
    )
    updated_at: str = Field(
        ...,
        description="ISO formatted timestamp of when the user was last updated",
        example="2024-03-20T09:15:00Z",
    )
    last_login: Optional[str] = Field(
        None,
        description="ISO formatted timestamp of user's last login",
        example="2024-03-22T16:45:00Z",
    )
    collection_ids: List[UUID] = Field(
        ...,
        description="List of collection IDs the user has access to",
        example=[
            "750e8400-e29b-41d4-a716-446655440000",
            "850e8400-e29b-41d4-a716-446655440000",
        ],
    )
    metadata: Optional[dict] = Field(
        None,
        description="Additional user metadata stored as key-value pairs",
        example={
            "department": "Engineering",
            "title": "Senior Developer",
            "location": "New York",
        },
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


class UserOverviewResponse(BaseModel):
    """Summary user information for list views"""

    id: UUID = Field(
        ...,
        description="Unique identifier for the user",
        example="550e8400-e29b-41d4-a716-446655440000",
    )
    username: str = Field(
        ..., description="User's login username", example="john.doe"
    )
    email: str = Field(
        ..., description="User's email address", example="john.doe@example.com"
    )
    is_active: bool = Field(
        ...,
        description="Whether the user account is currently active",
        example=True,
    )
    is_superuser: bool = Field(
        ...,
        description="Whether the user has superuser privileges",
        example=False,
    )
    collection_count: int = Field(
        ...,
        description="Total number of collections the user has access to",
        example=5,
    )
    created_at: str = Field(
        ...,
        description="ISO formatted timestamp of when the user was created",
        example="2024-03-15T14:30:00Z",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "username": "john.doe",
                "email": "john.doe@example.com",
                "is_active": True,
                "is_superuser": False,
                "collection_count": 5,
                "created_at": "2024-03-15T14:30:00Z",
            }
        }


class UserCollectionResponse(BaseModel):
    """Collection information associated with a user"""

    collection_id: UUID = Field(
        ...,
        description="Unique identifier for the collection",
        example="750e8400-e29b-41d4-a716-446655440000",
    )
    name: str = Field(
        ...,
        description="Name of the collection",
        example="Project Documentation",
    )
    description: Optional[str] = Field(
        None,
        description="Optional description of the collection",
        example="Technical documentation for the main project",
    )
    created_at: str = Field(
        ...,
        description="ISO formatted timestamp of when the collection was created",
        example="2024-03-15T14:30:00Z",
    )
    updated_at: str = Field(
        ...,
        description="ISO formatted timestamp of when the collection was last updated",
        example="2024-03-20T09:15:00Z",
    )
    document_count: int = Field(
        ...,
        description="Total number of documents in the collection",
        example=42,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "collection_id": "750e8400-e29b-41d4-a716-446655440000",
                "name": "Project Documentation",
                "description": "Technical documentation for the main project",
                "created_at": "2024-03-15T14:30:00Z",
                "updated_at": "2024-03-20T09:15:00Z",
                "document_count": 42,
            }
        }


class UserActivityResponse(BaseModel):
    """User activity statistics"""

    total_documents: int = Field(
        ...,
        description="Total number of documents owned by the user",
        example=156,
    )
    total_collections: int = Field(
        ...,
        description="Total number of collections the user has access to",
        example=8,
    )
    last_activity: Optional[str] = Field(
        None,
        description="ISO formatted timestamp of the user's last activity",
        example="2024-03-22T16:45:00Z",
    )
    recent_collections: List[UUID] = Field(
        ...,
        description="List of recently accessed collection IDs",
        example=[
            "750e8400-e29b-41d4-a716-446655440000",
            "850e8400-e29b-41d4-a716-446655440000",
        ],
    )
    recent_documents: List[UUID] = Field(
        ...,
        description="List of recently accessed document IDs",
        example=[
            "950e8400-e29b-41d4-a716-446655440000",
            "a50e8400-e29b-41d4-a716-446655440000",
        ],
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


class UsersRouter(BaseRouterV3):
    def __init__(
        self, providers, services, orchestration_provider=None, run_type=None
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _setup_routes(self):
        @self.router.get(
            "/users",
            summary="List Users",
            response_model=PaginatedResultsWrapper[List[UserOverviewResponse]],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# client.login(...)

# List users with filters
users = client.users.list(
    offset=0,
    limit=100,
    username="john",
    email="john@example.com",
    is_active=True,
    is_superuser=False,
    sort_by="created_at",
    sort_order="desc"
)""",
                    },
                    {
                        "lang": "Shell",
                        "source": """
curl -X GET "https://api.example.com/users?offset=0&limit=100&username=john&email=john@example.com&is_active=true&is_superuser=false&sort_by=created_at&sort_order=desc" \\
     -H "Authorization: Bearer YOUR_API_KEY"
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_users(
            offset: int = Query(0, ge=0, example=0),
            limit: int = Query(100, ge=1, le=1000, example=100),
            username: Optional[str] = Query(None, example="john"),
            email: Optional[str] = Query(None, example="john@example.com"),
            is_active: Optional[bool] = Query(None, example=True),
            is_superuser: Optional[bool] = Query(None, example=False),
            sort_by: Optional[str] = Query(
                None,
                example="created_at",
                description="Field to sort by (created_at, username, email)",
            ),
            sort_order: Optional[str] = Query(
                "desc",
                example="desc",
                description="Sort order (asc or desc)",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[List[UserOverviewResponse]]:
            """
            List all users with pagination and filtering options.
            Only accessible by superusers.

            Parameters:
            - offset: Number of items to skip
            - limit: Maximum number of items to return
            - username: Filter by username (partial match)
            - email: Filter by email (partial match)
            - is_active: Filter by active status
            - is_superuser: Filter by superuser status
            - sort_by: Field to sort by
            - sort_order: Sort order (asc/desc)
            """

            pass

        @self.router.get(
            "/users/{id}",
            summary="Get User Details",
            response_model=ResultsWrapper[UserResponse],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# client.login(...)

# Get user details
users = users.retrieve(
    id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
)
""",
                    },
                    {
                        "lang": "Shell",
                        "source": """
curl -X GET "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000" \\
     -H "Authorization: Bearer YOUR_API_KEY"
""",
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
        ) -> ResultsWrapper[UserResponse]:
            """
            Get detailed information about a specific user.
            Users can only access their own information unless they are superusers.
            """
            pass

        @self.router.get(
            "/users/{id}/collections",
            summary="Get User Collections",
            response_model=PaginatedResultsWrapper[
                List[UserCollectionResponse]
            ],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# client.login(...)

# Get user collections
collections = client.get_user_collections(
    "550e8400-e29b-41d4-a716-446655440000",
    offset=0,
    limit=100
)
""",
                    },
                    {
                        "lang": "Shell",
                        "source": """
curl -X GET "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/collections?offset=0&limit=100" \\
     -H "Authorization: Bearer YOUR_API_KEY"
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_user_collections(
            id: UUID = Path(
                ..., example="550e8400-e29b-41d4-a716-446655440000"
            ),
            offset: int = Query(0, ge=0, example=0),
            limit: int = Query(100, ge=1, le=1000, example=100),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[List[UserCollectionResponse]]:
            """
            Get all collections associated with a specific user.
            Users can only access their own collections unless they are superusers.
            """
            pass

        @self.router.post(
            "/users/{id}/collections/{collection_id}",
            summary="Add User to Collection",
            response_model=ResultsWrapper[None],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# client.login(...)

# Add user to collection
client.add_user_to_collection(
    "550e8400-e29b-41d4-a716-446655440000",
    "750e8400-e29b-41d4-a716-446655440000"
)
""",
                    },
                    {
                        "lang": "Shell",
                        "source": """
curl -X POST "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/collections/750e8400-e29b-41d4-a716-446655440000" \\
     -H "Authorization: Bearer YOUR_API_KEY"
""",
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
        ) -> ResultsWrapper[None]:
            """
            Add a user to a collection.
            Requires either superuser status or access to the collection.
            """
            pass

        @self.router.delete(
            "/users/{id}/collections/{collection_id}",
            summary="Remove User from Collection",
            response_model=ResultsWrapper[None],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# client.login(...)

# Remove user from collection
client.remove_user_from_collection(
    "550e8400-e29b-41d4-a716-446655440000",
    "750e8400-e29b-41d4-a716-446655440000"
)
""",
                    },
                    {
                        "lang": "Shell",
                        "source": """
curl -X DELETE "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000/collections/750e8400-e29b-41d4-a716-446655440000" \\
     -H "Authorization: Bearer YOUR_API_KEY"
""",
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
            pass

        @self.router.post(
            "/users/{id}",
            summary="Update User",
            response_model=ResultsWrapper[UserResponse],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
# client.login(...)

# Update user
updated_user = client.update_user(
    "550e8400-e29b-41d4-a716-446655440000",
    username="newusername",
    email="newemail@example.com",
    is_active=True,
    is_superuser=False,
    metadata={"department": "Engineering"}
)
""",
                    },
                    {
                        "lang": "Shell",
                        "source": """
curl -X POST "https://api.example.com/users/550e8400-e29b-41d4-a716-446655440000" \\
     -H "Authorization: Bearer YOUR_API_KEY" \\
     -H "Content-Type: application/json" \\
     -d '{
         "username": "newusername",
         "email": "newemail@example.com",
         "is_active": true,
         "is_superuser": false,
         "metadata": {"department": "Engineering"}
     }'
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_user(
            id: UUID = Path(...),
            username: Optional[str] = Body(None),
            email: Optional[str] = Body(None),
            is_active: Optional[bool] = Body(None),
            is_superuser: Optional[bool] = Body(None),
            metadata: Optional[dict] = Body(None),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[UserResponse]:
            """
            Update user information.
            Users can only update their own information unless they are superusers.
            Superuser status can only be modified by existing superusers.
            """
            pass
