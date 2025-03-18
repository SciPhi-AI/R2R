import logging
import textwrap
from typing import Optional, cast
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse

from core.base import GraphConstructionStatus, R2RException, Workflow
from core.base.abstractions import DocumentResponse, StoreType
from core.base.api.models import (
    GenericBooleanResponse,
    GenericMessageResponse,
    WrappedBooleanResponse,
    WrappedCommunitiesResponse,
    WrappedCommunityResponse,
    WrappedEntitiesResponse,
    WrappedEntityResponse,
    WrappedGenericMessageResponse,
    WrappedGraphResponse,
    WrappedGraphsResponse,
    WrappedRelationshipResponse,
    WrappedRelationshipsResponse,
)
from core.utils import (
    generate_default_user_collection_id,
    update_settings_from_dict,
)

from ...abstractions import R2RProviders, R2RServices
from ...config import R2RConfig
from .base_router import BaseRouterV3

logger = logging.getLogger()


class GraphRouter(BaseRouterV3):
    def __init__(
        self,
        providers: R2RProviders,
        services: R2RServices,
        config: R2RConfig,
    ):
        logging.info("Initializing GraphRouter")
        super().__init__(providers, services, config)
        self._register_workflows()

    def _register_workflows(self):
        workflow_messages = {}
        if self.providers.orchestration.config.provider == "hatchet":
            workflow_messages["graph-extraction"] = (
                "Document extraction task queued successfully."
            )
            workflow_messages["graph-clustering"] = (
                "Graph enrichment task queued successfully."
            )
            workflow_messages["graph-deduplication"] = (
                "Entity deduplication task queued successfully."
            )
        else:
            workflow_messages["graph-extraction"] = (
                "Document entities and relationships extracted successfully."
            )
            workflow_messages["graph-clustering"] = (
                "Graph communities created successfully."
            )
            workflow_messages["graph-deduplication"] = (
                "Entity deduplication completed successfully."
            )

        self.providers.orchestration.register_workflows(
            Workflow.GRAPH,
            self.services.graph,
            workflow_messages,
        )

    async def _get_collection_id(
        self, collection_id: Optional[UUID], auth_user
    ) -> UUID:
        """Helper method to get collection ID, using default if none
        provided."""
        if collection_id is None:
            return generate_default_user_collection_id(auth_user.id)
        return collection_id

    def _setup_routes(self):
        @self.router.get(
            "/graphs",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="List graphs",
            openapi_extra={
                "x-codeSamples": [
                    {  # TODO: Verify
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.list()
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.list({});
                            }

                            main();
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_graphs(
            collection_ids: list[str] = Query(
                [],
                description="A list of graph IDs to retrieve. If not provided, all graphs will be returned.",
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
        ) -> WrappedGraphsResponse:
            """Returns a paginated list of graphs the authenticated user has
            access to.

            Results can be filtered by providing specific graph IDs. Regular
            users will only see graphs they own or have access to. Superusers
            can see all graphs.

            The graphs are returned in order of last modification, with most
            recent first.
            """
            requesting_user_id = (
                None if auth_user.is_superuser else [auth_user.id]
            )

            graph_uuids = [UUID(graph_id) for graph_id in collection_ids]

            list_graphs_response = await self.services.graph.list_graphs(
                # user_ids=requesting_user_id,
                graph_ids=graph_uuids,
                offset=offset,
                limit=limit,
            )

            return (  # type: ignore
                list_graphs_response["results"],
                {"total_entries": list_graphs_response["total_entries"]},
            )

        @self.router.get(
            "/graphs/{collection_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Retrieve graph details",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.get(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.retrieve({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_graph(
            collection_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGraphResponse:
            """Retrieves detailed information about a specific graph by ID."""
            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection associated with the given graph.",
                    403,
                )

            list_graphs_response = await self.services.graph.list_graphs(
                # user_ids=None,
                graph_ids=[collection_id],
                offset=0,
                limit=1,
            )
            return list_graphs_response["results"][0]  # type: ignore

        @self.router.post(
            "/graphs/{collection_id}/communities/build",
            dependencies=[Depends(self.rate_limit_dependency)],
        )
        @self.base_endpoint
        async def build_communities(
            collection_id: UUID = Path(
                ..., description="The unique identifier of the collection"
            ),
            graph_enrichment_settings: Optional[dict] = Body(
                default=None,
                description="Settings for the graph enrichment process.",
            ),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGenericMessageResponse:
            """Creates communities in the graph by analyzing entity
            relationships and similarities.

            Communities are created through the following process:
            1. Analyzes entity relationships and metadata to build a similarity graph
            2. Applies advanced community detection algorithms (e.g. Leiden) to identify densely connected groups
            3. Creates hierarchical community structure with multiple granularity levels
            4. Generates natural language summaries and statistical insights for each community

            The resulting communities can be used to:
            - Understand high-level graph structure and organization
            - Identify key entity groupings and their relationships
            - Navigate and explore the graph at different levels of detail
            - Generate insights about entity clusters and their characteristics

            The community detection process is configurable through settings like:
                - Community detection algorithm parameters
                - Summary generation prompt
            """
            collections_overview_response = (
                await self.services.management.collections_overview(
                    user_ids=[auth_user.id],
                    collection_ids=[collection_id],
                    offset=0,
                    limit=1,
                )
            )["results"]
            if len(collections_overview_response) == 0:  # type: ignore
                raise R2RException("Collection not found.", 404)

            # Check user permissions for graph
            if (
                not auth_user.is_superuser
                and collections_overview_response[0].owner_id != auth_user.id  # type: ignore
            ):
                raise R2RException(
                    "Only superusers can `build communities` for a graph they do not own.",
                    403,
                )

            # If no collection ID is provided, use the default user collection
            # id = generate_default_user_collection_id(auth_user.id)

            # Apply runtime settings overrides
            server_graph_enrichment_settings = (
                self.providers.database.config.graph_enrichment_settings
            )
            if graph_enrichment_settings:
                server_graph_enrichment_settings = update_settings_from_dict(
                    server_graph_enrichment_settings, graph_enrichment_settings
                )

            workflow_input = {
                "collection_id": str(collection_id),
                "graph_enrichment_settings": server_graph_enrichment_settings.model_dump_json(),
                "user": auth_user.json(),
            }

            if run_with_orchestration:
                try:
                    return await self.providers.orchestration.run_workflow(  # type: ignore
                        "graph-clustering", {"request": workflow_input}, {}
                    )
                    return GenericMessageResponse(
                        message="Graph communities created successfully."
                    )  # type: ignore

                except Exception as e:  # TODO: Need to find specific error (gRPC most likely?)
                    logger.error(
                        f"Error running orchestrated community building: {e} \n\nAttempting to run without orchestration."
                    )
            from core.main.orchestration import (
                simple_graph_search_results_factory,
            )

            logger.info("Running build-communities without orchestration.")
            simple_graph_search_results = simple_graph_search_results_factory(
                self.services.graph
            )
            await simple_graph_search_results["graph-clustering"](
                workflow_input
            )
            return {  # type: ignore
                "message": "Graph communities created successfully.",
                "task_id": None,
            }

        @self.router.post(
            "/graphs/{collection_id}/reset",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Reset a graph back to the initial state.",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.reset(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.reset({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/reset" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def reset(
            collection_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Deletes a graph and all its associated data.

            This endpoint permanently removes the specified graph along with
            all entities and relationships that belong to only this graph. The
            original source entities and relationships extracted from
            underlying documents are not deleted and are managed through the
            document lifecycle.
            """
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can reset a graph", 403)

            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            await self.services.graph.reset_graph(id=collection_id)
            # await _pull(collection_id, auth_user)
            return GenericBooleanResponse(success=True)  # type: ignore

        # update graph
        @self.router.post(
            "/graphs/{collection_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Update graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.update(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                graph={
                                    "name": "New Name",
                                    "description": "New Description"
                                }
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.update({
                                    collection_id: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    name: "New Name",
                                    description: "New Description",
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_graph(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to update",
            ),
            name: Optional[str] = Body(
                None, description="The name of the graph"
            ),
            description: Optional[str] = Body(
                None, description="An optional description of the graph"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGraphResponse:
            """Update an existing graphs's configuration.

            This endpoint allows updating the name and description of an
            existing collection. The user must have appropriate permissions to
            modify the collection.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can update graph details", 403
                )

            if (
                not auth_user.is_superuser
                and id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            return await self.services.graph.update_graph(  # type: ignore
                collection_id,
                name=name,
                description=description,
            )

        @self.router.get(
            "/graphs/{collection_id}/entities",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.list_entities(collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7")
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.listEntities({
                                    collection_id: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                });
                            }

                            main();
                            """),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def get_entities(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to list entities from.",
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
        ) -> WrappedEntitiesResponse:
            """Lists all entities in the graph with pagination support."""
            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            entities, count = await self.services.graph.get_entities(
                parent_id=collection_id,
                offset=offset,
                limit=limit,
            )

            return entities, {  # type: ignore
                "total_entries": count,
            }

        @self.router.post(
            "/graphs/{collection_id}/entities/export",
            summary="Export graph entities to CSV",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            response = client.graphs.export_entities(
                                collection_id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                output_path="export.csv",
                                columns=["id", "title", "created_at"],
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
                                await client.graphs.exportEntities({
                                    collectionId: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    outputPath: "export.csv",
                                    columns: ["id", "title", "created_at"],
                                    includeHeader: true,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "http://127.0.0.1:7272/v3/graphs/export_entities" \
                            -H "Authorization: Bearer YOUR_API_KEY" \
                            -H "Content-Type: application/json" \
                            -H "Accept: text/csv" \
                            -d '{ "columns": ["id", "title", "created_at"], "include_header": true }' \
                            --output export.csv
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def export_entities(
            background_tasks: BackgroundTasks,
            collection_id: UUID = Path(
                ...,
                description="The ID of the collection to export entities from.",
            ),
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
            """Export documents as a downloadable CSV file."""

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can export data.",
                    403,
                )

            (
                csv_file_path,
                temp_file,
            ) = await self.services.management.export_graph_entities(
                id=collection_id,
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
                filename="documents_export.csv",
            )

        @self.router.post(
            "/graphs/{collection_id}/entities",
            dependencies=[Depends(self.rate_limit_dependency)],
        )
        @self.base_endpoint
        async def create_entity(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to add the entity to.",
            ),
            name: str = Body(
                ..., description="The name of the entity to create."
            ),
            description: str = Body(
                ..., description="The description of the entity to create."
            ),
            category: Optional[str] = Body(
                None, description="The category of the entity to create."
            ),
            metadata: Optional[dict] = Body(
                None, description="The metadata of the entity to create."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedEntityResponse:
            """Creates a new entity in the graph."""
            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            return await self.services.graph.create_entity(  # type: ignore
                name=name,
                description=description,
                parent_id=collection_id,
                category=category,
                metadata=metadata,
            )

        @self.router.post(
            "/graphs/{collection_id}/relationships",
            dependencies=[Depends(self.rate_limit_dependency)],
        )
        @self.base_endpoint
        async def create_relationship(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to add the relationship to.",
            ),
            subject: str = Body(
                ..., description="The subject of the relationship to create."
            ),
            subject_id: UUID = Body(
                ...,
                description="The ID of the subject of the relationship to create.",
            ),
            predicate: str = Body(
                ..., description="The predicate of the relationship to create."
            ),
            object: str = Body(
                ..., description="The object of the relationship to create."
            ),
            object_id: UUID = Body(
                ...,
                description="The ID of the object of the relationship to create.",
            ),
            description: str = Body(
                ...,
                description="The description of the relationship to create.",
            ),
            weight: float = Body(
                1.0, description="The weight of the relationship to create."
            ),
            metadata: Optional[dict] = Body(
                None, description="The metadata of the relationship to create."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedRelationshipResponse:
            """Creates a new relationship in the graph."""
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can create relationships.", 403
                )

            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )
            return await self.services.graph.create_relationship(  # type: ignore
                subject=subject,
                subject_id=subject_id,
                predicate=predicate,
                object=object,
                object_id=object_id,
                description=description,
                weight=weight,
                metadata=metadata,
                parent_id=collection_id,
            )

        @self.router.post(
            "/graphs/{collection_id}/relationships/export",
            summary="Export graph relationships to CSV",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            response = client.graphs.export_entities(
                                collection_id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                output_path="export.csv",
                                columns=["id", "title", "created_at"],
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
                                await client.graphs.exportEntities({
                                    collectionId: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    outputPath: "export.csv",
                                    columns: ["id", "title", "created_at"],
                                    includeHeader: true,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "http://127.0.0.1:7272/v3/graphs/export_relationships" \
                            -H "Authorization: Bearer YOUR_API_KEY" \
                            -H "Content-Type: application/json" \
                            -H "Accept: text/csv" \
                            -d '{ "columns": ["id", "title", "created_at"], "include_header": true }' \
                            --output export.csv
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def export_relationships(
            background_tasks: BackgroundTasks,
            collection_id: UUID = Path(
                ...,
                description="The ID of the document to export entities from.",
            ),
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
            """Export documents as a downloadable CSV file."""

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can export data.",
                    403,
                )

            (
                csv_file_path,
                temp_file,
            ) = await self.services.management.export_graph_relationships(
                id=collection_id,
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
                filename="documents_export.csv",
            )

        @self.router.get(
            "/graphs/{collection_id}/entities/{entity_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.get_entity(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                entity_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.get_entity({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    entityId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_entity(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph containing the entity.",
            ),
            entity_id: UUID = Path(
                ..., description="The ID of the entity to retrieve."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedEntityResponse:
            """Retrieves a specific entity by its ID."""
            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            result = await self.providers.database.graphs_handler.entities.get(
                parent_id=collection_id,
                store_type=StoreType.GRAPHS,
                offset=0,
                limit=1,
                entity_ids=[entity_id],
            )
            if len(result) == 0 or len(result[0]) == 0:
                raise R2RException("Entity not found", 404)
            return result[0][0]

        @self.router.post(
            "/graphs/{collection_id}/entities/{entity_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
        )
        @self.base_endpoint
        async def update_entity(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph containing the entity.",
            ),
            entity_id: UUID = Path(
                ..., description="The ID of the entity to update."
            ),
            name: Optional[str] = Body(
                ..., description="The updated name of the entity."
            ),
            description: Optional[str] = Body(
                None, description="The updated description of the entity."
            ),
            category: Optional[str] = Body(
                None, description="The updated category of the entity."
            ),
            metadata: Optional[dict] = Body(
                None, description="The updated metadata of the entity."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedEntityResponse:
            """Updates an existing entity in the graph."""
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can update graph entities.", 403
                )
            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            return await self.services.graph.update_entity(  # type: ignore
                entity_id=entity_id,
                name=name,
                category=category,
                description=description,
                metadata=metadata,
            )

        @self.router.delete(
            "/graphs/{collection_id}/entities/{entity_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Remove an entity",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.remove_entity(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                entity_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.removeEntity({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    entityId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_entity(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to remove the entity from.",
            ),
            entity_id: UUID = Path(
                ...,
                description="The ID of the entity to remove from the graph.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Removes an entity from the graph."""
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can delete graph details.", 403
                )

            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            await self.services.graph.delete_entity(
                parent_id=collection_id,
                entity_id=entity_id,
            )

            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.get(
            "/graphs/{collection_id}/relationships",
            dependencies=[Depends(self.rate_limit_dependency)],
            description="Lists all relationships in the graph with pagination support.",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.list_relationships(collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7")
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.listRelationships({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                });
                            }

                            main();
                            """),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def get_relationships(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to list relationships from.",
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
        ) -> WrappedRelationshipsResponse:
            """Lists all relationships in the graph with pagination support."""
            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            relationships, count = await self.services.graph.get_relationships(
                parent_id=collection_id,
                offset=offset,
                limit=limit,
            )

            return relationships, {  # type: ignore
                "total_entries": count,
            }

        @self.router.get(
            "/graphs/{collection_id}/relationships/{relationship_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            description="Retrieves a specific relationship by its ID.",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.get_relationship(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                relationship_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.getRelationship({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    relationshipId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                                });
                            }

                            main();
                            """),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def get_relationship(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph containing the relationship.",
            ),
            relationship_id: UUID = Path(
                ..., description="The ID of the relationship to retrieve."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedRelationshipResponse:
            """Retrieves a specific relationship by its ID."""
            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            results = (
                await self.providers.database.graphs_handler.relationships.get(
                    parent_id=collection_id,
                    store_type=StoreType.GRAPHS,
                    offset=0,
                    limit=1,
                    relationship_ids=[relationship_id],
                )
            )
            if len(results) == 0 or len(results[0]) == 0:
                raise R2RException("Relationship not found", 404)
            return results[0][0]

        @self.router.post(
            "/graphs/{collection_id}/relationships/{relationship_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
        )
        @self.base_endpoint
        async def update_relationship(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph containing the relationship.",
            ),
            relationship_id: UUID = Path(
                ..., description="The ID of the relationship to update."
            ),
            subject: Optional[str] = Body(
                ..., description="The updated subject of the relationship."
            ),
            subject_id: Optional[UUID] = Body(
                ..., description="The updated subject ID of the relationship."
            ),
            predicate: Optional[str] = Body(
                ..., description="The updated predicate of the relationship."
            ),
            object: Optional[str] = Body(
                ..., description="The updated object of the relationship."
            ),
            object_id: Optional[UUID] = Body(
                ..., description="The updated object ID of the relationship."
            ),
            description: Optional[str] = Body(
                None,
                description="The updated description of the relationship.",
            ),
            weight: Optional[float] = Body(
                None, description="The updated weight of the relationship."
            ),
            metadata: Optional[dict] = Body(
                None, description="The updated metadata of the relationship."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedRelationshipResponse:
            """Updates an existing relationship in the graph."""
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can update graph details", 403
                )

            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            return await self.services.graph.update_relationship(  # type: ignore
                relationship_id=relationship_id,
                subject=subject,
                subject_id=subject_id,
                predicate=predicate,
                object=object,
                object_id=object_id,
                description=description,
                weight=weight,
                metadata=metadata,
            )

        @self.router.delete(
            "/graphs/{collection_id}/relationships/{relationship_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            description="Removes a relationship from the graph.",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.delete_relationship(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                relationship_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.deleteRelationship({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    relationshipId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                                });
                            }

                            main();
                            """),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def delete_relationship(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to remove the relationship from.",
            ),
            relationship_id: UUID = Path(
                ...,
                description="The ID of the relationship to remove from the graph.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Removes a relationship from the graph."""
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can delete a relationship.", 403
                )

            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            await self.services.graph.delete_relationship(
                parent_id=collection_id,
                relationship_id=relationship_id,
            )

            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/graphs/{collection_id}/communities",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Create a new community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.create_community(
                                collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                name="My Community",
                                summary="A summary of the community",
                                findings=["Finding 1", "Finding 2"],
                                rating=5,
                                rating_explanation="This is a rating explanation",
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.createCommunity({
                                    collectionId: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    name: "My Community",
                                    summary: "A summary of the community",
                                    findings: ["Finding 1", "Finding 2"],
                                    rating: 5,
                                    ratingExplanation: "This is a rating explanation",
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_community(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to create the community in.",
            ),
            name: str = Body(..., description="The name of the community"),
            summary: str = Body(..., description="A summary of the community"),
            findings: Optional[list[str]] = Body(
                default=[], description="Findings about the community"
            ),
            rating: Optional[float] = Body(
                default=5, ge=1, le=10, description="Rating between 1 and 10"
            ),
            rating_explanation: Optional[str] = Body(
                default="", description="Explanation for the rating"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedCommunityResponse:
            """Creates a new community in the graph.

            While communities are typically built automatically via the /graphs/{id}/communities/build endpoint,
            this endpoint allows you to manually create your own communities.

            This can be useful when you want to:
            - Define custom groupings of entities based on domain knowledge
            - Add communities that weren't detected by the automatic process
            - Create hierarchical organization structures
            - Tag groups of entities with specific metadata

            The created communities will be integrated with any existing automatically detected communities
            in the graph's community structure.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can create a community.", 403
                )

            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            return await self.services.graph.create_community(  # type: ignore
                parent_id=collection_id,
                name=name,
                summary=summary,
                findings=findings,
                rating=rating,
                rating_explanation=rating_explanation,
            )

        @self.router.get(
            "/graphs/{collection_id}/communities",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="List communities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.list_communities(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.listCommunities({
                                    collectionId: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_communities(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to get communities for.",
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
        ) -> WrappedCommunitiesResponse:
            """Lists all communities in the graph with pagination support."""
            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            communities, count = await self.services.graph.get_communities(
                parent_id=collection_id,
                offset=offset,
                limit=limit,
            )

            return communities, {  # type: ignore
                "total_entries": count,
            }

        @self.router.get(
            "/graphs/{collection_id}/communities/{community_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Retrieve a community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.get_community(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.getCommunity({
                                    collectionId: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_community(
            collection_id: UUID = Path(
                ...,
                description="The ID of the collection to get communities for.",
            ),
            community_id: UUID = Path(
                ...,
                description="The ID of the community to get.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedCommunityResponse:
            """Retrieves a specific community by its ID."""
            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            results = (
                await self.providers.database.graphs_handler.communities.get(
                    parent_id=collection_id,
                    community_ids=[community_id],
                    store_type=StoreType.GRAPHS,
                    offset=0,
                    limit=1,
                )
            )
            if len(results) == 0 or len(results[0]) == 0:
                raise R2RException("Community not found", 404)
            return results[0][0]

        @self.router.delete(
            "/graphs/{collection_id}/communities/{community_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Delete a community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.delete_community(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                community_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.graphs.deleteCommunity({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    communityId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_community(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to delete the community from.",
            ),
            community_id: UUID = Path(
                ...,
                description="The ID of the community to delete.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.graph_ids
            ):
                raise R2RException(
                    "Only superusers can delete communities", 403
                )

            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            await self.services.graph.delete_community(
                parent_id=collection_id,
                community_id=community_id,
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/graphs/{collection_id}/communities/export",
            summary="Export document communities to CSV",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            response = client.graphs.export_communities(
                                collection_id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                output_path="export.csv",
                                columns=["id", "title", "created_at"],
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
                                await client.graphs.exportCommunities({
                                    collectionId: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    outputPath: "export.csv",
                                    columns: ["id", "title", "created_at"],
                                    includeHeader: true,
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent("""
                            curl -X POST "http://127.0.0.1:7272/v3/graphs/export_communities" \
                            -H "Authorization: Bearer YOUR_API_KEY" \
                            -H "Content-Type: application/json" \
                            -H "Accept: text/csv" \
                            -d '{ "columns": ["id", "title", "created_at"], "include_header": true }' \
                            --output export.csv
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def export_communities(
            background_tasks: BackgroundTasks,
            collection_id: UUID = Path(
                ...,
                description="The ID of the document to export entities from.",
            ),
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
            """Export documents as a downloadable CSV file."""

            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can export data.",
                    403,
                )

            (
                csv_file_path,
                temp_file,
            ) = await self.services.management.export_graph_communities(
                id=collection_id,
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
                filename="documents_export.csv",
            )

        @self.router.post(
            "/graphs/{collection_id}/communities/{community_id}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Update community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.update_community(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                community_update={
                                    "metadata": {
                                        "topic": "Technology",
                                        "description": "Tech companies and products"
                                    }
                                }
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            async function main() {
                                const response = await client.graphs.updateCommunity({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    communityId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    communityUpdate: {
                                        metadata: {
                                            topic: "Technology",
                                            description: "Tech companies and products"
                                        }
                                    }
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_community(
            collection_id: UUID = Path(...),
            community_id: UUID = Path(...),
            name: Optional[str] = Body(None),
            summary: Optional[str] = Body(None),
            findings: Optional[list[str]] = Body(None),
            rating: Optional[float] = Body(default=None, ge=1, le=10),
            rating_explanation: Optional[str] = Body(None),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedCommunityResponse:
            """Updates an existing community in the graph."""
            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.graph_ids
            ):
                raise R2RException(
                    "Only superusers can update communities.", 403
                )

            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            return await self.services.graph.update_community(  # type: ignore
                community_id=community_id,
                name=name,
                summary=summary,
                findings=findings,
                rating=rating,
                rating_explanation=rating_explanation,
            )

        @self.router.post(
            "/graphs/{collection_id}/pull",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Pull latest entities to the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            response = client.graphs.pull(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )"""),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            async function main() {
                                const response = await client.graphs.pull({
                                    collection_id: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def pull(
            collection_id: UUID = Path(
                ..., description="The ID of the graph to initialize."
            ),
            force: Optional[bool] = Body(
                False,
                description="If true, forces a re-pull of all entities and relationships.",
            ),
            # document_ids: list[UUID] = Body(
            #     ..., description="List of document IDs to add to the graph."
            # ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Adds documents to a graph by copying their entities and
            relationships.

            This endpoint:
            1. Copies document entities to the graphs_entities table
            2. Copies document relationships to the graphs_relationships table
            3. Associates the documents with the graph

            When a document is added:
            - Its entities and relationships are copied to graph-specific tables
            - Existing entities/relationships are updated by merging their properties
            - The document ID is recorded in the graph's document_ids array

            Documents added to a graph will contribute their knowledge to:
            - Graph analysis and querying
            - Community detection
            - Knowledge graph enrichment

            The user must have access to both the graph and the documents being added.
            """

            collections_overview_response = (
                await self.services.management.collections_overview(
                    user_ids=[auth_user.id],
                    collection_ids=[collection_id],
                    offset=0,
                    limit=1,
                )
            )["results"]
            if len(collections_overview_response) == 0:  # type: ignore
                raise R2RException("Collection not found.", 404)

            # Check user permissions for graph
            if (
                not auth_user.is_superuser
                and collections_overview_response[0].owner_id != auth_user.id  # type: ignore
            ):
                raise R2RException("Only superusers can `pull` a graph.", 403)

            if (
                # not auth_user.is_superuser
                collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the collection associated with the given graph.",
                    403,
                )

            list_graphs_response = await self.services.graph.list_graphs(
                # user_ids=None,
                graph_ids=[collection_id],
                offset=0,
                limit=1,
            )
            if len(list_graphs_response["results"]) == 0:  # type: ignore
                raise R2RException("Graph not found", 404)
            collection_id = list_graphs_response["results"][0].collection_id  # type: ignore
            documents: list[DocumentResponse] = []
            document_req = await self.providers.database.collections_handler.documents_in_collection(
                collection_id, offset=0, limit=100
            )
            results = cast(list[DocumentResponse], document_req["results"])
            documents.extend(results)

            while len(results) == 100:
                document_req = await self.providers.database.collections_handler.documents_in_collection(
                    collection_id, offset=len(documents), limit=100
                )
                results = cast(list[DocumentResponse], document_req["results"])
                documents.extend(results)

            success = False

            for document in documents:
                entities = (
                    await self.providers.database.graphs_handler.entities.get(
                        parent_id=document.id,
                        store_type=StoreType.DOCUMENTS,
                        offset=0,
                        limit=100,
                    )
                )
                has_document = (
                    await self.providers.database.graphs_handler.has_document(
                        collection_id, document.id
                    )
                )
                if has_document:
                    logger.info(
                        f"Document {document.id} is already in graph {collection_id}, skipping."
                    )
                    continue
                if len(entities[0]) == 0:
                    if not force:
                        logger.warning(
                            f"Document {document.id} has no entities, extraction may not have been called, skipping."
                        )
                        continue
                    else:
                        logger.warning(
                            f"Document {document.id} has no entities, but force=True, continuing."
                        )

                success = (
                    await self.providers.database.graphs_handler.add_documents(
                        id=collection_id,
                        document_ids=[document.id],
                    )
                )
            if not success:
                logger.warning(
                    f"No documents were added to graph {collection_id}, marking as failed."
                )

            if success:
                await self.providers.database.documents_handler.set_workflow_status(
                    id=collection_id,
                    status_type="graph_sync_status",
                    status=GraphConstructionStatus.SUCCESS,
                )

            return GenericBooleanResponse(success=success)  # type: ignore
