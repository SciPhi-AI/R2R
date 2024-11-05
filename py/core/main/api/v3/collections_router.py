import logging
import textwrap
from typing import List, Optional, Union
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel, Field

from core.base import R2RException, RunType
from core.base.api.models import (
    ResultsWrapper,
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
    name: str = Field(..., description="The name of the collection")
    description: Optional[str] = Field(
        None, description="An optional description of the collection"
    )


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
        @self.router.post(
            "/collections",
            summary="Create a new collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.create(
                                name="My New Collection",
                                description="This is a sample collection"
                            )
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/collections" \\
                                 -H "Content-Type: application/json" \\
                                 -H "Authorization: Bearer YOUR_API_KEY" \\
                                 -d '{"name": "My New Collection", "description": "This is a sample collection"}'
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_collection(
            config: CollectionConfig = Body(
                ..., description="The configuration for the new collection"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCollectionResponse:
            """
            Create a new collection and automatically add the creating user to it.

            This endpoint allows authenticated users to create a new collection with a specified name
            and optional description. The user creating the collection is automatically added as a member.
            """
            collection = await self.services["management"].create_collection(
                name=config.name, description=config.description
            )
            # Add the creating user to the collection
            await self.services["management"].add_user_to_collection(
                auth_user.id, collection.collection_id
            )
            print("collection = ", collection)
            return collection

        @self.router.get(
            "/collections",
            summary="List collections",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.list(
                                offset=0,
                                limit=10,
                                name="Sample",
                                sort_by="created_at",
                                sort_order="desc"
                            )
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/collections?offset=0&limit=10&name=Sample&sort_by=created_at&sort_order=desc" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_collections(
            offset: int = Query(
                0,
                ge=0,
                description="The number of collections to skip (for pagination)",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="The maximum number of collections to return (1-1000)",
            ),
            name: Optional[str] = Query(
                None,
                description="Filter collections by name (case-insensitive partial match)",
            ),
            sort_by: Optional[str] = Query(
                None, description="The field to sort the results by"
            ),
            sort_order: Optional[str] = Query(
                "desc",
                description="The order to sort the results ('asc' or 'desc')",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCollectionListResponse:
            """
            List collections the user has access to with pagination and filtering options.

            This endpoint returns a paginated list of collections that the authenticated user has access to.
            It supports filtering by collection name and sorting options.
            """

            list_collections_response = await self.services[
                "management"
            ].list_collections(offset=offset, limit=min(max(limit, 1), 1000))

            return list_collections_response["results"], {
                "total_entries": list_collections_response["total_entries"]
            }

        @self.router.get(
            "/collections/{id}",
            summary="Get collection details",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.get("123e4567-e89b-12d3-a456-426614174000")
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_collection(
            id: UUID = Path(
                ..., description="The unique identifier of the collection"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCollectionResponse:
            """
            Get details of a specific collection.

            This endpoint retrieves detailed information about a single collection identified by its UUID.
            The user must have access to the collection to view its details.
            """
            if (
                not auth_user.is_superuser
                and id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            result = await self.services["management"].get_collection(id)
            return result

        @self.router.post(
            "/collections/{id}",
            summary="Update collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.update(
                                "123e4567-e89b-12d3-a456-426614174000",
                                name="Updated Collection Name",
                                description="Updated description"
                            )
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000" \\
                                 -H "Content-Type: application/json" \\
                                 -H "Authorization: Bearer YOUR_API_KEY" \\
                                 -d '{"name": "Updated Collection Name", "description": "Updated description"}'
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_collection(
            id: UUID = Path(
                ...,
                description="The unique identifier of the collection to update",
            ),
            config: CollectionConfig = Body(
                ..., description="The new configuration for the collection"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCollectionResponse:
            """
            Update an existing collection's configuration.

            This endpoint allows updating the name and description of an existing collection.
            The user must have appropriate permissions to modify the collection.
            """
            if (
                not auth_user.is_superuser
                and id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            return await self.services["management"].update_collection(
                id, name=config.name, description=config.description
            )

        @self.router.delete(
            "/collections/{id}",
            summary="Delete collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.delete("123e4567-e89b-12d3-a456-426614174000")
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_collection(
            id: UUID = Path(
                ...,
                description="The unique identifier of the collection to delete",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[bool]:
            """
            Delete an existing collection.

            This endpoint allows deletion of a collection identified by its UUID.
            The user must have appropriate permissions to delete the collection.
            Deleting a collection removes all associations but does not delete the documents within it.
            """
            if (
                not auth_user.is_superuser
                and id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            await self.services["management"].delete_collection(id)
            return True, {}

        @self.router.post(
            "/collections/{id}/documents/{document_id}",
            summary="Add document to collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.add_document(
                                "123e4567-e89b-12d3-a456-426614174000",
                                "456e789a-b12c-34d5-e678-901234567890"
                            )
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/documents/456e789a-b12c-34d5-e678-901234567890" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """
                        ),
                    },
                ]
            },
        )
        async def add_document_to_collection(
            id: UUID = Path(...),
            document_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedAddUserResponse:
            """
            Add a document to a collection.
            """
            if (
                not auth_user.is_superuser
                and id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            result = await self.services[
                "management"
            ].assign_document_to_collection(document_id, id)
            return result

        @self.router.get(
            "/collections/{id}/documents",
            summary="List documents in collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.list_documents(
                                "123e4567-e89b-12d3-a456-426614174000",
                                offset=0,
                                limit=10,
                                sort_by="created_at",
                                sort_order="desc"
                            )
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/documents?offset=0&limit=10&sort_by=created_at&sort_order=desc" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_collection_documents(
            id: UUID = Path(
                ..., description="The unique identifier of the collection"
            ),
            offset: int = Query(
                0,
                ge=0,
                description="The number of documents to skip (for pagination)",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="The maximum number of documents to return (1-1000)",
            ),
            sort_by: Optional[str] = Query(
                None, description="The field to sort the documents by"
            ),
            sort_order: Optional[str] = Query(
                "desc",
                description="The order to sort the documents ('asc' or 'desc')",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedDocumentOverviewResponse:
            """
            Get all documents in a collection with pagination and sorting options.

            This endpoint retrieves a paginated list of documents associated with a specific collection.
            It supports sorting options to customize the order of returned documents.
            """
            if (
                not auth_user.is_superuser
                and id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            documents_in_collection_response = await self.services[
                "management"
            ].documents_in_collection(id, offset, limit)

            return documents_in_collection_response["results"], {
                "total_entries": documents_in_collection_response[
                    "total_entries"
                ]
            }

        @self.base_endpoint
        async def add_document_to_collection(
            id: UUID = Path(
                ..., description="The unique identifier of the collection"
            ),
            document_id: UUID = Path(
                ..., description="The unique identifier of the document to add"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedAddUserResponse:
            """
            Add a document to a collection.

            This endpoint associates an existing document with a collection.
            The user must have permissions to modify the collection and access to the document.

            Args:
                id (UUID): The unique identifier of the collection.
                document_id (UUID): The unique identifier of the document to add.
                auth_user: The authenticated user making the request.

            Returns:
                WrappedAddUserResponse: Confirmation of the document addition to the collection.

            Raises:
                R2RException: If the collection or document is not found, or if the user lacks necessary permissions.
            """
            pass

        @self.router.delete(
            "/collections/{id}/documents/{document_id}",
            summary="Remove document from collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.remove_document(
                                "123e4567-e89b-12d3-a456-426614174000",
                                "456e789a-b12c-34d5-e678-901234567890"
                            )
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/documents/456e789a-b12c-34d5-e678-901234567890" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def remove_document_from_collection(
            id: UUID = Path(
                ..., description="The unique identifier of the collection"
            ),
            document_id: UUID = Path(
                ...,
                description="The unique identifier of the document to remove",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[bool]:
            """
            Remove a document from a collection.

            This endpoint removes the association between a document and a collection.
            It does not delete the document itself. The user must have permissions to modify the collection.
            """
            if (
                not auth_user.is_superuser
                and id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            await self.services["management"].add_document_to_collection(
                document_id, id
            )
            return True, {}

        @self.router.get(
            "/collections/{id}/users",
            summary="List users in collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.list_users(
                                "123e4567-e89b-12d3-a456-426614174000",
                                offset=0,
                                limit=10,
                                sort_by="username",
                                sort_order="asc"
                            )
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/users?offset=0&limit=10&sort_by=username&sort_order=asc" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_collection_users(
            id: UUID = Path(
                ..., description="The unique identifier of the collection"
            ),
            offset: int = Query(
                0,
                ge=0,
                description="The number of users to skip (for pagination)",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="The maximum number of users to return (1-1000)",
            ),
            sort_by: Optional[str] = Query(
                None, description="The field to sort the users by"
            ),
            sort_order: Optional[str] = Query(
                "desc",
                description="The order to sort the users ('asc' or 'desc')",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedUsersInCollectionResponse:
            """
            Get all users in a collection with pagination and sorting options.

            This endpoint retrieves a paginated list of users who have access to a specific collection.
            It supports sorting options to customize the order of returned users.
            """
            if (
                not auth_user.is_superuser
                and id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            users_in_collection_response = await self.services[
                "management"
            ].get_users_in_collection(
                collection_id=id,
                offset=offset,
                limit=min(max(limit, 1), 1000),
            )

            return users_in_collection_response["results"], {
                "total_entries": users_in_collection_response["total_entries"]
            }

        @self.router.post(
            "/collections/{id}/users/{user_id}",
            summary="Add user to collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.add_user(
                                "123e4567-e89b-12d3-a456-426614174000",
                                "789a012b-c34d-5e6f-g789-012345678901"
                            )
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/users/789a012b-c34d-5e6f-g789-012345678901" \\
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
                ..., description="The unique identifier of the collection"
            ),
            user_id: UUID = Path(
                ..., description="The unique identifier of the user to add"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedAddUserResponse:
            """
            Add a user to a collection.

            This endpoint grants a user access to a specific collection.
            The authenticated user must have admin permissions for the collection to add new users.
            """
            if (
                not auth_user.is_superuser
                and id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            result = await self.services["management"].add_user_to_collection(
                user_id, id
            )
            return result

        @self.router.delete(
            "/collections/{id}/users/{user_id}",
            summary="Remove user from collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.remove_user(
                                "123e4567-e89b-12d3-a456-426614174000",
                                "789a012b-c34d-5e6f-g789-012345678901"
                            )
                        """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/users/789a012b-c34d-5e6f-g789-012345678901" \\
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
                ..., description="The unique identifier of the collection"
            ),
            user_id: UUID = Path(
                ..., description="The unique identifier of the user to remove"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[bool]:
            """
            Remove a user from a collection.

            This endpoint revokes a user's access to a specific collection.
            The authenticated user must have admin permissions for the collection to remove users.
            """
            if (
                not auth_user.is_superuser
                and id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            await self.services["management"].remove_user_from_collection(
                user_id, id
            )
            return True
