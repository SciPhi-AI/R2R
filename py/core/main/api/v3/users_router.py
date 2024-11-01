import logging
from typing import List, Optional
from uuid import UUID
from fastapi import Depends, Path, Query, Body
from pydantic import Json

from core.base import R2RException
from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper
from .base_router import BaseRouterV3
import datetime
from pydantic import BaseModel, Field

class UserResponse(BaseModel):
    """Detailed user information response"""
    id: UUID
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    created_at: str
    updated_at: str
    last_login: Optional[str]
    collection_ids: List[UUID]
    metadata: Optional[dict]

class UserOverviewResponse(BaseModel):
    """Summary user information for list views"""
    id: UUID
    username: str
    email: str
    is_active: bool
    is_superuser: bool
    collection_count: int
    created_at: str

class UserCollectionResponse(BaseModel):
    """Collection information associated with a user"""
    collection_id: UUID
    name: str
    description: Optional[str]
    created_at: str
    updated_at: str
    document_count: int

class UserActivityResponse(BaseModel):
    """User activity statistics"""
    total_documents: int
    total_collections: int
    last_activity: Optional[str]
    recent_collections: List[UUID]
    recent_documents: List[UUID]

logger = logging.getLogger()

class UsersRouter(BaseRouterV3):
    def __init__(self, providers, services, orchestration_provider=None, run_type=None):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _setup_routes(self):
        @self.router.get("/users")
        @self.base_endpoint
        async def list_users(
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            username: Optional[str] = Query(None),
            email: Optional[str] = Query(None),
            is_active: Optional[bool] = Query(None),
            is_superuser: Optional[bool] = Query(None),
            sort_by: Optional[str] = Query("created_at"),
            sort_order: Optional[str] = Query("desc"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[List[UserOverviewResponse]]:
            """
            List all users with pagination and filtering options.
            Only accessible by superusers.
            """
            pass

        @self.router.get("/users/{user_id}")
        @self.base_endpoint
        async def get_user(
            user_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[UserResponse]:
            """
            Get detailed information about a specific user.
            Users can only access their own information unless they are superusers.
            """
            pass

        @self.router.get("/users/{user_id}/activity")
        @self.base_endpoint
        async def get_user_activity(
            user_id: UUID = Path(...),
            start_date: Optional[str] = Query(None),
            end_date: Optional[str] = Query(None),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[UserActivityResponse]:
            """
            Get activity statistics for a specific user.
            Users can only access their own activity unless they are superusers.
            """
            pass

        @self.router.get("/users/{user_id}/collections")
        @self.base_endpoint
        async def get_user_collections(
            user_id: UUID = Path(...),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[List[UserCollectionResponse]]:
            """
            Get all collections associated with a specific user.
            Users can only access their own collections unless they are superusers.
            """
            pass

        @self.router.post("/users/{user_id}/collections/{collection_id}")
        @self.base_endpoint
        async def add_user_to_collection(
            user_id: UUID = Path(...),
            collection_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[None]:
            """
            Add a user to a collection.
            Requires either superuser status or access to the collection.
            """
            pass

        @self.router.delete("/users/{user_id}/collections/{collection_id}")
        @self.base_endpoint
        async def remove_user_from_collection(
            user_id: UUID = Path(...),
            collection_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[None]:
            """
            Remove a user from a collection.
            Requires either superuser status or access to the collection.
            """
            pass

        @self.router.patch("/users/{user_id}")
        @self.base_endpoint
        async def update_user(
            user_id: UUID = Path(...),
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

        @self.router.post("/users/{user_id}/deactivate")
        @self.base_endpoint
        async def deactivate_user(
            user_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[UserResponse]:
            """
            Deactivate a user account.
            Only accessible by superusers.
            """
            pass

        @self.router.post("/users/{user_id}/reactivate")
        @self.base_endpoint
        async def reactivate_user(
            user_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[UserResponse]:
            """
            Reactivate a deactivated user account.
            Only accessible by superusers.
            """
            pass