import logging
from typing import List, Optional, Union
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel

from core.base import R2RException, RunType
from core.base.api.models import (
    WrappedAddUserResponse,
    WrappedCollectionListResponse,
    WrappedCollectionResponse,
    WrappedDeleteResponse,
    WrappedDocumentOverviewResponse,
    WrappedUsersInCollectionResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper

from .base_router import BaseRouterV3

logger = logging.getLogger()


class CollectionConfig(BaseModel):
    name: str
    description: Optional[str] = None


class CollectionsRouter(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: Union[
            HatchetOrchestrationProvider, SimpleOrchestrationProvider
        ],
        run_type: RunType = RunType.MANAGEMENT,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _setup_routes(self):
        @self.router.post("/collections")
        @self.base_endpoint
        async def create_collection(
            config: CollectionConfig = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCollectionResponse:
            """
            Create a new collection and automatically add the creating user to it.
            """
            pass

        @self.router.get("/collections")
        @self.base_endpoint
        async def list_collections(
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            name: Optional[str] = Query(None),
            sort_by: Optional[str] = Query(None),
            sort_order: Optional[str] = Query("desc"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCollectionListResponse:
            """
            List collections the user has access to with pagination and filtering options.
            """
            pass

        @self.router.get("/collections/{id}")
        @self.base_endpoint
        async def get_collection(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCollectionResponse:
            """
            Get details of a specific collection.
            """
            pass

        @self.router.post("/collections/{id}")
        @self.base_endpoint
        async def update_collection(
            id: UUID = Path(...),
            config: CollectionConfig = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCollectionResponse:
            """
            Update an existing collection's configuration.
            """
            pass

        @self.router.delete("/collections/{id}")
        @self.base_endpoint
        async def delete_collection(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedDeleteResponse:
            """
            Delete an existing collection.
            """
            pass

        @self.router.get("/collections/{id}/documents")
        @self.base_endpoint
        async def get_collection_documents(
            id: UUID = Path(...),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            sort_by: Optional[str] = Query(None),
            sort_order: Optional[str] = Query("desc"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedDocumentOverviewResponse:
            """
            Get all documents in a collection with pagination and sorting options.
            """
            pass

        @self.router.post("/collections/{id}/documents/{document_id}")
        @self.base_endpoint
        async def add_document_to_collection(
            id: UUID = Path(...),
            document_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedAddUserResponse:
            """
            Add a document to a collection.
            """
            pass

        @self.router.delete("/collections/{id}/documents/{document_id}")
        @self.base_endpoint
        async def remove_document_from_collection(
            id: UUID = Path(...),
            document_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedDeleteResponse:
            """
            Remove a document from a collection.
            """
            pass

        @self.router.get("/collections/{id}/users")
        @self.base_endpoint
        async def get_collection_users(
            id: UUID = Path(...),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            sort_by: Optional[str] = Query(None),
            sort_order: Optional[str] = Query("desc"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedUsersInCollectionResponse:
            """
            Get all users in a collection with pagination and sorting options.
            """
            pass

        @self.router.post("/collections/{id}/users/{user_id}")
        @self.base_endpoint
        async def add_user_to_collection(
            id: UUID = Path(...),
            user_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedAddUserResponse:
            """
            Add a user to a collection.
            """
            pass

        @self.router.delete("/collections/{id}/users/{user_id}")
        @self.base_endpoint
        async def remove_user_from_collection(
            id: UUID = Path(...),
            user_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedDeleteResponse:
            """
            Remove a user from a collection.
            """
            pass
