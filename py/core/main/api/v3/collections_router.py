import logging
import textwrap
from enum import Enum
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse

from core.base import R2RException
from core.base.abstractions import GraphCreationSettings
from core.base.api.models import (
    GenericBooleanResponse,
    WrappedBooleanResponse,
    WrappedCollectionResponse,
    WrappedCollectionsResponse,
    WrappedDocumentsResponse,
    WrappedGenericMessageResponse,
    WrappedUsersResponse,
)
from core.utils import (
    generate_default_user_collection_id,
    update_settings_from_dict,
)

from ...abstractions import R2RProviders, R2RServices
from ...config import R2RConfig
from .base_router import BaseRouterV3

logger = logging.getLogger()


class CollectionAction(str, Enum):
    VIEW = "view"
    EDIT = "edit"
    DELETE = "delete"
    MANAGE_USERS = "manage_users"
    ADD_DOCUMENT = "add_document"
    REMOVE_DOCUMENT = "remove_document"


async def authorize_collection_action(
    auth_user, collection_id: UUID, action: CollectionAction, services
) -> bool:
    """Authorize a user's action on a given collection based on:

    - If user is superuser (admin): Full access.
    - If user is owner of the collection: Full access.
    - If user is a member of the collection (in `collection_ids`): VIEW only.
    - Otherwise: No access.
    """

    # Superusers have complete access
    if auth_user.is_superuser:
        return True

    # Fetch collection details: owner_id and members
    results = (
        await services.management.collections_overview(
            0, 1, collection_ids=[collection_id]
        )
    )["results"]
    if len(results) == 0:
        raise R2RException("The specified collection does not exist.", 404)
    details = results[0]
    owner_id = details.owner_id

    # Check if user is owner
    if auth_user.id == owner_id:
        # Owner can do all actions
        return True

    # Check if user is a member (non-owner)
    if collection_id in auth_user.collection_ids:
        # Members can only view
        if action == CollectionAction.VIEW:
            return True
        else:
            raise R2RException(
                "Insufficient permissions for this action.", 403
            )

    # User is neither owner nor member
    raise R2RException("You do not have access to this collection.", 403)


class CollectionsRouter(BaseRouterV3):
    def __init__(
        self, providers: R2RProviders, services: R2RServices, config: R2RConfig
    ):
        logging.info("Initializing CollectionsRouter")
        super().__init__(providers, services, config)

    def _setup_routes(self):
        @self.router.post(
            "/collections",
            summary="Create a new collection",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.create(
                                name="My New Collection",
                                description="This is a sample collection"
                            )
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.create({
                                    name: "My New Collection",
                                    description: "This is a sample collection"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/collections" \\
                                 -H "Content-Type: application/json" \\
                                 -H "Authorization: Bearer YOUR_API_KEY" \\
                                 -d '{"name": "My New Collection", "description": "This is a sample collection"}'
                        """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_collection(
            name: str = Body(..., description="The name of the collection"),
            description: Optional[str] = Body(
                None, description="An optional description of the collection"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedCollectionResponse:
            """Create a new collection and automatically add the creating user
            to it.

            This endpoint allows authenticated users to create a new collection
            with a specified name and optional description. The user creating
            the collection is automatically added as a member.
            """
            user_collections_count = (
                await self.services.management.collections_overview(
                    user_ids=[auth_user.id], limit=1, offset=0
                )
            )["total_entries"]
            user_max_collections = (
                await self.services.management.get_user_max_collections(
                    auth_user.id
                )
            )
            if (user_collections_count + 1) >= user_max_collections:  # type: ignore
                raise R2RException(
                    f"User has reached the maximum number of collections allowed ({user_max_collections}).",
                    400,
                )
            collection = await self.services.management.create_collection(
                owner_id=auth_user.id,
                name=name,
                description=description,
            )
            # Add the creating user to the collection
            await self.services.management.add_user_to_collection(
                auth_user.id, collection.id
            )
            return collection  # type: ignore

        @self.router.post(
            "/collections/export",
            summary="Export collections to CSV",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            response = client.collections.export(
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
                                await client.collections.export({
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
                            curl -X POST "http://127.0.0.1:7272/v3/collections/export" \
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
        async def export_collections(
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
            """Export collections as a CSV file."""

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can export data.",
                    403,
                )

            (
                csv_file_path,
                temp_file,
            ) = await self.services.management.export_collections(
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
                filename="collections_export.csv",
            )

        @self.router.get(
            "/collections",
            summary="List collections",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.list(
                                offset=0,
                                limit=10,
                            )
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.list();
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/collections?offset=0&limit=10&name=Sample" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_collections(
            ids: list[str] = Query(
                [],
                description="A list of collection IDs to retrieve. If not provided, all collections will be returned.",
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
            """Returns a paginated list of collections the authenticated user
            has access to.

            Results can be filtered by providing specific collection IDs.
            Regular users will only see collections they own or have access to.
            Superusers can see all collections.

            The collections are returned in order of last modification, with
            most recent first.
            """
            requesting_user_id = (
                None if auth_user.is_superuser else [auth_user.id]
            )

            collection_uuids = [UUID(collection_id) for collection_id in ids]

            collections_overview_response = (
                await self.services.management.collections_overview(
                    user_ids=requesting_user_id,
                    collection_ids=collection_uuids,
                    offset=offset,
                    limit=limit,
                )
            )

            return (  # type: ignore
                collections_overview_response["results"],
                {
                    "total_entries": collections_overview_response[
                        "total_entries"
                    ]
                },
            )

        @self.router.get(
            "/collections/{id}",
            summary="Get collection details",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.retrieve("123e4567-e89b-12d3-a456-426614174000")
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.retrieve({id: "123e4567-e89b-12d3-a456-426614174000"});
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_collection(
            id: UUID = Path(
                ..., description="The unique identifier of the collection"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedCollectionResponse:
            """Get details of a specific collection.

            This endpoint retrieves detailed information about a single
            collection identified by its UUID. The user must have access to the
            collection to view its details.
            """
            await authorize_collection_action(
                auth_user, id, CollectionAction.VIEW, self.services
            )

            collections_overview_response = (
                await self.services.management.collections_overview(
                    user_ids=None,
                    collection_ids=[id],
                    offset=0,
                    limit=1,
                )
            )
            overview = collections_overview_response["results"]

            if len(overview) == 0:  # type: ignore
                raise R2RException(
                    "The specified collection does not exist.",
                    404,
                )
            return overview[0]  # type: ignore

        @self.router.post(
            "/collections/{id}",
            summary="Update collection",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.update(
                                "123e4567-e89b-12d3-a456-426614174000",
                                name="Updated Collection Name",
                                description="Updated description"
                            )
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.update({
                                    id: "123e4567-e89b-12d3-a456-426614174000",
                                    name: "Updated Collection Name",
                                    description: "Updated description"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000" \\
                                 -H "Content-Type: application/json" \\
                                 -H "Authorization: Bearer YOUR_API_KEY" \\
                                 -d '{"name": "Updated Collection Name", "description": "Updated description"}'
                        """),
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
            name: Optional[str] = Body(
                None, description="The name of the collection"
            ),
            description: Optional[str] = Body(
                None, description="An optional description of the collection"
            ),
            generate_description: Optional[bool] = Body(
                False,
                description="Whether to generate a new synthetic description for the collection",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedCollectionResponse:
            """Update an existing collection's configuration.

            This endpoint allows updating the name and description of an
            existing collection. The user must have appropriate permissions to
            modify the collection.
            """
            await authorize_collection_action(
                auth_user, id, CollectionAction.EDIT, self.services
            )

            if generate_description and description is not None:
                raise R2RException(
                    "Cannot provide both a description and request to synthetically generate a new one.",
                    400,
                )

            return await self.services.management.update_collection(  # type: ignore
                id,
                name=name,
                description=description,
                generate_description=generate_description or False,
            )

        @self.router.delete(
            "/collections/{id}",
            summary="Delete collection",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.delete("123e4567-e89b-12d3-a456-426614174000")
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.delete({id: "123e4567-e89b-12d3-a456-426614174000"});
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X DELETE "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Delete an existing collection.

            This endpoint allows deletion of a collection identified by its
            UUID. The user must have appropriate permissions to delete the
            collection. Deleting a collection removes all associations but does
            not delete the documents within it.
            """
            if id == generate_default_user_collection_id(auth_user.id):
                raise R2RException(
                    "Cannot delete the default user collection.",
                    400,
                )
            await authorize_collection_action(
                auth_user, id, CollectionAction.DELETE, self.services
            )

            await self.services.management.delete_collection(collection_id=id)
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/collections/{id}/documents/{document_id}",
            summary="Add document to collection",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.add_document(
                                "123e4567-e89b-12d3-a456-426614174000",
                                "456e789a-b12c-34d5-e678-901234567890"
                            )
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.addDocument({
                                    id: "123e4567-e89b-12d3-a456-426614174000"
                                    documentId: "456e789a-b12c-34d5-e678-901234567890"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/documents/456e789a-b12c-34d5-e678-901234567890" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def add_document_to_collection(
            id: UUID = Path(...),
            document_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGenericMessageResponse:
            """Add a document to a collection."""
            await authorize_collection_action(
                auth_user, id, CollectionAction.ADD_DOCUMENT, self.services
            )

            return (
                await self.services.management.assign_document_to_collection(
                    document_id, id
                )
            )

        @self.router.get(
            "/collections/{id}/documents",
            summary="List documents in collection",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.list_documents(
                                "123e4567-e89b-12d3-a456-426614174000",
                                offset=0,
                                limit=10,
                            )
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.listDocuments({id: "123e4567-e89b-12d3-a456-426614174000"});
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/documents?offset=0&limit=10" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """),
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
                description="Specifies the number of objects to skip. Defaults to 0.",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedDocumentsResponse:
            """Get all documents in a collection with pagination and sorting
            options.

            This endpoint retrieves a paginated list of documents associated
            with a specific collection. It supports sorting options to
            customize the order of returned documents.
            """
            await authorize_collection_action(
                auth_user, id, CollectionAction.VIEW, self.services
            )

            documents_in_collection_response = (
                await self.services.management.documents_in_collection(
                    id, offset, limit
                )
            )

            return documents_in_collection_response["results"], {  # type: ignore
                "total_entries": documents_in_collection_response[
                    "total_entries"
                ]
            }

        @self.router.delete(
            "/collections/{id}/documents/{document_id}",
            summary="Remove document from collection",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.remove_document(
                                "123e4567-e89b-12d3-a456-426614174000",
                                "456e789a-b12c-34d5-e678-901234567890"
                            )
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.removeDocument({
                                    id: "123e4567-e89b-12d3-a456-426614174000"
                                    documentId: "456e789a-b12c-34d5-e678-901234567890"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X DELETE "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/documents/456e789a-b12c-34d5-e678-901234567890" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Remove a document from a collection.

            This endpoint removes the association between a document and a
            collection. It does not delete the document itself. The user must
            have permissions to modify the collection.
            """
            await authorize_collection_action(
                auth_user, id, CollectionAction.REMOVE_DOCUMENT, self.services
            )
            await self.services.management.remove_document_from_collection(
                document_id, id
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.get(
            "/collections/{id}/users",
            summary="List users in collection",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.list_users(
                                "123e4567-e89b-12d3-a456-426614174000",
                                offset=0,
                                limit=10,
                            )
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.listUsers({
                                    id: "123e4567-e89b-12d3-a456-426614174000"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/users?offset=0&limit=10" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """),
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
            """Get all users in a collection with pagination and sorting
            options.

            This endpoint retrieves a paginated list of users who have access
            to a specific collection. It supports sorting options to customize
            the order of returned users.
            """
            await authorize_collection_action(
                auth_user, id, CollectionAction.VIEW, self.services
            )

            users_in_collection_response = (
                await self.services.management.get_users_in_collection(
                    collection_id=id,
                    offset=offset,
                    limit=min(max(limit, 1), 1000),
                )
            )

            return users_in_collection_response["results"], {  # type: ignore
                "total_entries": users_in_collection_response["total_entries"]
            }

        @self.router.post(
            "/collections/{id}/users/{user_id}",
            summary="Add user to collection",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.add_user(
                                "123e4567-e89b-12d3-a456-426614174000",
                                "789a012b-c34d-5e6f-g789-012345678901"
                            )
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.addUser({
                                    id: "123e4567-e89b-12d3-a456-426614174000"
                                    userId: "789a012b-c34d-5e6f-g789-012345678901"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/users/789a012b-c34d-5e6f-g789-012345678901" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Add a user to a collection.

            This endpoint grants a user access to a specific collection. The
            authenticated user must have admin permissions for the collection
            to add new users.
            """
            await authorize_collection_action(
                auth_user, id, CollectionAction.MANAGE_USERS, self.services
            )

            result = await self.services.management.add_user_to_collection(
                user_id, id
            )
            return GenericBooleanResponse(success=result)  # type: ignore

        @self.router.delete(
            "/collections/{id}/users/{user_id}",
            summary="Remove user from collection",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.collections.remove_user(
                                "123e4567-e89b-12d3-a456-426614174000",
                                "789a012b-c34d-5e6f-g789-012345678901"
                            )
                        """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.collections.removeUser({
                                    id: "123e4567-e89b-12d3-a456-426614174000"
                                    userId: "789a012b-c34d-5e6f-g789-012345678901"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X DELETE "https://api.example.com/v3/collections/123e4567-e89b-12d3-a456-426614174000/users/789a012b-c34d-5e6f-g789-012345678901" \\
                                 -H "Authorization: Bearer YOUR_API_KEY"
                        """),
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
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Remove a user from a collection.

            This endpoint revokes a user's access to a specific collection. The
            authenticated user must have admin permissions for the collection
            to remove users.
            """
            await authorize_collection_action(
                auth_user, id, CollectionAction.MANAGE_USERS, self.services
            )

            result = (
                await self.services.management.remove_user_from_collection(
                    user_id, id
                )
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/collections/{id}/extract",
            summary="Extract entities and relationships",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            result = client.documents.extract(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
                            )
                            """),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def extract(
            id: UUID = Path(
                ...,
                description="The ID of the document to extract entities and relationships from.",
            ),
            settings: Optional[GraphCreationSettings] = Body(
                default=None,
                description="Settings for the entities and relationships extraction process.",
            ),
            run_with_orchestration: Optional[bool] = Query(
                default=True,
                description="Whether to run the entities and relationships extraction process with orchestration.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGenericMessageResponse:
            """Extracts entities and relationships from a document.

            The entities and relationships extraction process involves:
            1. Parsing documents into semantic chunks
            2. Extracting entities and relationships using LLMs
            """
            await authorize_collection_action(
                auth_user, id, CollectionAction.EDIT, self.services
            )

            settings = settings.dict() if settings else None  # type: ignore
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            # Apply runtime settings overrides
            server_graph_creation_settings = (
                self.providers.database.config.graph_creation_settings
            )

            if settings:
                server_graph_creation_settings = update_settings_from_dict(
                    server_settings=server_graph_creation_settings,
                    settings_dict=settings,  # type: ignore
                )
            if run_with_orchestration:
                try:
                    workflow_input = {
                        "collection_id": str(id),
                        "graph_creation_settings": server_graph_creation_settings.model_dump_json(),
                        "user": auth_user.json(),
                    }

                    return await self.providers.orchestration.run_workflow(  # type: ignore
                        "graph-extraction", {"request": workflow_input}, {}
                    )
                except Exception as e:  # TODO: Need to find specific error (gRPC most likely?)
                    logger.error(
                        f"Error running orchestrated extraction: {e} \n\nAttempting to run without orchestration."
                    )

            from core.main.orchestration import (
                simple_graph_search_results_factory,
            )

            logger.info("Running extract-triples without orchestration.")
            simple_graph_search_results = simple_graph_search_results_factory(
                self.services.graph
            )
            await simple_graph_search_results["graph-extraction"](
                workflow_input
            )  # type: ignore
            return {  # type: ignore
                "message": "Graph created successfully.",
                "task_id": None,
            }

        @self.router.get(
            "/collections/name/{collection_name}",
            summary="Get a collection by name",
            dependencies=[Depends(self.rate_limit_dependency)],
        )
        @self.base_endpoint
        async def get_collection_by_name(
            collection_name: str = Path(
                ..., description="The name of the collection"
            ),
            owner_id: Optional[UUID] = Query(
                None,
                description="(Superuser only) Specify the owner_id to retrieve a collection by name",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedCollectionResponse:
            """Retrieve a collection by its (owner_id, name) combination.

            The authenticated user can only fetch collections they own, or, if
            superuser, from anyone.
            """
            if auth_user.is_superuser:
                if not owner_id:
                    owner_id = auth_user.id
            else:
                owner_id = auth_user.id

            # If not superuser, fetch by (owner_id, name). Otherwise, maybe pass `owner_id=None`.
            # Decide on the logic for superusers.
            if not owner_id:  # is_superuser
                # If you want superusers to do /collections/name/<string>?owner_id=...
                # just parse it from the query. For now, let's say it's not implemented.
                raise R2RException(
                    "Superuser must specify an owner_id to fetch by name.", 400
                )

            collection = await self.providers.database.collections_handler.get_collection_by_name(
                owner_id, collection_name
            )
            if not collection:
                raise R2RException("Collection not found.", 404)

            # Now, authorize the 'view' action just in case:
            # e.g. await authorize_collection_action(auth_user, collection.id, CollectionAction.VIEW, self.services)

            return collection  # type: ignore
