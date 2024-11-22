import logging
import textwrap
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query

from core.base import R2RException, RunType
from core.base.abstractions import DataLevel, KGRunType

from core.base.api.models import (
    GenericBooleanResponse,
    WrappedBooleanResponse,
    WrappedKGCreationResponse,
    WrappedGenericMessageResponse,
    WrappedGraphResponse,
    WrappedGraphsResponse,
    WrappedKGEntityDeduplicationResponse,
    WrappedKGTunePromptResponse,
)


from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from core.utils import (
    update_settings_from_dict,
)

from core.base.abstractions import (
    Entity,
    KGCreationSettings,
    Relationship,
    GraphBuildSettings,
)

from .base_router import BaseRouterV3

from fastapi import Request

logger = logging.getLogger()

from enum import Enum


class GraphObjectType(str, Enum):
    ENTITIES = "entities"
    RELATIONSHIPS = "relationships"
    COLLECTIONS = "collections"
    DOCUMENTS = "documents"

    def __str__(self):
        return self.value


class GraphRouter(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: (
            HatchetOrchestrationProvider | SimpleOrchestrationProvider
        ),
        run_type: RunType = RunType.KG,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _get_path_level(self, request: Request) -> DataLevel:
        path = request.url.path
        if "/chunks/" in path:
            return DataLevel.CHUNK
        elif "/documents/" in path:
            return DataLevel.DOCUMENT
        else:
            return DataLevel.GRAPH

    async def _deduplicate_entities(
        self,
        id: UUID,
        settings,
        run_type: Optional[KGRunType] = KGRunType.ESTIMATE,
        run_with_orchestration: bool = True,
        auth_user=None,
    ) -> WrappedKGEntityDeduplicationResponse:
        """Deduplicates entities in the knowledge graph using LLM-based analysis.

        The deduplication process:
        1. Groups potentially duplicate entities by name/type
        2. Uses LLM analysis to determine if entities refer to same thing
        3. Merges duplicate entities while preserving relationships
        4. Updates all references to use canonical entity IDs

        Args:
            id (UUID): Graph containing the entities
            settings (dict, optional): Deduplication settings including:
                - kg_entity_deduplication_type (str): Deduplication method (e.g. "by_name")
                - kg_entity_deduplication_prompt (str): Custom prompt for analysis
                - max_description_input_length (int): Max chars for entity descriptions
                - generation_config (dict): LLM generation parameters
            run_type (KGRunType): Whether to estimate cost or run deduplication
            run_with_orchestration (bool): Whether to run async with task queue
            auth_user: Authenticated user making request

        Returns:
            Result containing:
                message (str): Status message
                task_id (UUID): Async task ID if run with orchestration

        Raises:
            R2RException: If user unauthorized or deduplication fails
        """
        if not auth_user.is_superuser:
            raise R2RException("Only superusers can deduplicate entities", 403)

        server_settings = (
            self.providers.database.config.kg_entity_deduplication_settings
        )
        if settings:
            server_settings = update_settings_from_dict(
                server_settings, settings
            )

        # Return cost estimate if requested
        if run_type == KGRunType.ESTIMATE:
            return await self.services["kg"].get_deduplication_estimate(
                id, server_settings
            )

        workflow_input = {
            "graph_id": str(id),
            "kg_entity_deduplication_settings": server_settings.model_dump_json(),
            "user": auth_user.model_dump_json(),
        }

        if run_with_orchestration:
            return await self.orchestration_provider.run_workflow(  # type: ignore
                "entity-deduplication", {"request": workflow_input}, {}
            )
        else:
            from core.main.orchestration import simple_kg_factory

            simple_kg = simple_kg_factory(self.services["kg"])
            await simple_kg["entity-deduplication"](workflow_input)
            return {  # type: ignore
                "message": "Entity deduplication completed successfully.",
                "task_id": None,
            }

    def _setup_routes(self):

        @self.router.post(
            "/graphs",
            summary="Create a new graph",
            openapi_extra={
                "x-codeSamples": [
                    {  # TODO: Verify
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.create(
                                graph={
                                    "name": "New Graph",
                                    "description": "New Description"
                                }
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
                                const response = await client.graphs.create({
                                    name: "New Graph",
                                    description: "New Description",
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
        async def create_graph(
            name: str = Body(..., description="The name of the graph"),
            description: Optional[str] = Body(
                None, description="An optional description of the graph"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGraphResponse:
            """
            Creates a new empty graph.

            This is the first step in building a knowledge graph. After creating the graph, you can:

            1. Add data to the graph:
               - Manually add entities and relationships via the /entities and /relationships endpoints
               - Automatically extract entities and relationships from documents via the /graphs/{id}/documents endpoint

            2. Build communities:
               - Build communities of related entities via the /graphs/{id}/communities/build endpoint

            3. Update graph metadata:
               - Modify the graph name, description and settings via the /graphs/{id} endpoint

            The graph ID returned by this endpoint is required for all subsequent operations on the graph.
            """

            return await self.services["kg"].create_new_graph(
                user_id=auth_user.id,
                name=name,
                description=description,
            )

        @self.router.get(
            "/graphs",
            summary="List graphs",
            openapi_extra={
                "x-codeSamples": [
                    {  # TODO: Verify
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.create(
                                graph={
                                    "name": "New Graph",
                                    "description": "New Description"
                                }
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
                                const response = await client.graphs.list();
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
            ids: list[str] = Query(
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGraphsResponse:
            """
            Returns a paginated list of graphs the authenticated user has access to.

            Results can be filtered by providing specific graph IDs. Regular users will only see
            graphs they own or have access to. Superusers can see all graphs.

            The graphs are returned in order of last modification, with most recent first.
            """
            requesting_user_id = (
                None if auth_user.is_superuser else [auth_user.id]
            )

            graph_uuids = [UUID(graph_id) for graph_id in ids]

            list_graphs_response = await self.services["kg"].list_graphs(
                user_ids=requesting_user_id,
                graph_ids=graph_uuids,
                offset=offset,
                limit=limit,
            )

            return (  # type: ignore
                list_graphs_response["results"],
                {"total_entries": list_graphs_response["total_entries"]},
            )

        @self.router.get(
            "/graphs/{id}",
            summary="Retrieve graph details",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.get(
                                id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
                                const response = await client.graphs.retrieve({
                                    id: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
                            curl -X GET "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_graph(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGraphResponse:
            """
            Retrieves detailed information about a specific graph by ID.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to access this graph.",
                    403,
                )

            list_graphs_response = await self.services["kg"].list_graphs(
                user_ids=None,
                graph_ids=[id],
                offset=0,
                limit=1,
            )
            return list_graphs_response["results"][0]

        @self.router.delete(
            "/graphs/{id}",
            summary="Delete a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.delete(
                                id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
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
                                const response = await client.graphs.delete({
                                    id: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_graph(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Deletes a graph and all its associated data.

            This endpoint permanently removes the specified graph along with all
            entities and relationships that belong to only this graph.
            Entities and relationships extracted from documents are not deleted
            and must be deleted separately using the /entities and /relationships
            endpoints.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to delete this graph.",
                    403,
                )

            await self.services["kg"].delete_graph_v3(id=id)
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/graphs/{id}",
            summary="Update graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.update(
                                id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                graph={
                                    "name": "New Name",
                                    "description": "New Description"
                                }
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
                                const response = await client.graphs.update({
                                    id: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    name: "New Name",
                                    description: "New Description",
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
        async def update_graph(
            id: UUID = Path(
                ...,
                description="The unique identifier of the graph to update",
            ),
            name: Optional[str] = Body(
                None, description="The name of the graph"
            ),
            description: Optional[str] = Body(
                None, description="An optional description of the graph"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Update an existing graphs's configuration.

            This endpoint allows updating the name and description of an existing collection.
            The user must have appropriate permissions to modify the collection.
            """
            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to update this graph.",
                    403,
                )

            return await self.services["kg"].update_graph(  # type: ignore
                graph_id=id,
                name=name,
                description=description,
            )

        @self.router.post(
            "/graphs/{id}/tune-prompt",
            summary="Tune a graph-related prompt",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.tune_prompt(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                prompt_name="graphrag_relationships_extraction_few_shot",
                                documents_limit=100,
                                chunks_limit=1000
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/tune-prompt" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "prompt_name": "graphrag_relationships_extraction_few_shot",
                                    "documents_limit": 100,
                                    "chunks_limit": 1000
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        # FIXME: This should be refactored to use the document summaries
        async def tune_prompt(
            id: UUID = Path(...),
            prompt_name: str = Body(
                ...,
                description="The prompt to tune. Valid options: graphrag_relationships_extraction_few_shot, graphrag_entity_description, graphrag_communities",
            ),
            documents_offset: int = Body(0, ge=0),
            documents_limit: int = Body(100, ge=1),
            chunks_offset: int = Body(0, ge=0),
            chunks_limit: int = Body(100, ge=1),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGTunePromptResponse:
            """Tunes a graph operation prompt using collection data.

            Uses sample documents and chunks from the collection to tune prompts for:
            - Entity and relationship extraction
            - Entity description generation
            - Community report generation
            """
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can tune prompts", 403)

            tuned_prompt = await self.services["kg"].tune_prompt(
                prompt_name=prompt_name,
                collection_id=id,
                documents_offset=documents_offset,
                documents_limit=documents_limit,
                chunks_offset=chunks_offset,
                chunks_limit=chunks_limit,
            )

            return tuned_prompt  # type: ignore

        @self.router.post(
            "/graphs/{id}/entities/{entity_id}",
            summary="Add entities to the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.graphs.add_entity(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                entity_id="123e4567-e89b-12d3-a456-426614174000",
                            ])
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
                                const response = await client.graphs.addEntity({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    entityId: "123e4567-e89b-12d3-a456-426614174000",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def add_entity_to_graph(
            id: UUID = Path(...),
            entity_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGenericMessageResponse:
            """
            Adds an entity to the graph by its ID.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to add an entity to this graph.",
                    403,
                )

            if not await self.services["management"].has_entity_access(
                auth_user, entity_id
            ):
                raise R2RException(
                    "You do not have permission to add this entity to the graph.",
                    403,
                )

            return await self.services["kg"].add_entity_to_graph(
                graph_id=id,
                entity_id=entity_id,
            )

        @self.router.delete(
            "/graphs/{id}/entities/{entity_id}",
            summary="Remove an entity from the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.graphs.remove_entities(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_ids=[
                                "123e4567-e89b-12d3-a456-426614174000",
                                "123e4567-e89b-12d3-a456-426614174001",
                            ])
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
                                const response = await client.graphs.removeEntity({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    entityId: "123e4567-e89b-12d3-a456-426614174000",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def remove_entity_from_graph(
            id: UUID = Path(...),
            entity_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Removes an entity to the graph by its ID.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to remove an entity from this graph.",
                    403,
                )

            if not await self.services["management"].has_entity_access(
                auth_user, entity_id
            ):
                raise R2RException(
                    "You do not have permission to remove this entity from the graph.",
                    403,
                )

            await self.services["kg"].remove_entity_from_graph(
                graph_id=id,
                entity_id=entity_id,
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/graphs/{id}/relationships/{relationship_id}",
            summary="Add relationships to the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.graphs.add_relationship(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                relationship_id="123e4567-e89b-12d3-a456-426614174000"
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
                                const response = await client.graphs.addRelationship({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    relationshipId: "123e4567-e89b-12d3-a456-426614174000",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def add_relationship_to_graph(
            id: UUID = Path(
                ...,
                description="The ID of the graph to add the relationship to.",
            ),
            relationship_id: UUID = Path(
                ...,
                description="The ID of the relationship to add to the graph.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGenericMessageResponse:
            """
            Adds a relationship to the graph by its ID.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to add a relationship to this graph.",
                    403,
                )

            if not await self.services["management"].has_relationship_access(
                auth_user, relationship_id
            ):
                raise R2RException(
                    "You do not have permission to add this relationship to the graph.",
                    403,
                )

            return await self.services["kg"].add_relationship_to_graph(
                graph_id=id, relationship_id=relationship_id
            )

        @self.router.delete(
            "/graphs/{id}/relationships/{relationship_id}",
            summary="Remove a relationship from the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.graphs.remove_relationship(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                relationship_id="123e4567-e89b-12d3-a456-426614174000"
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
                                const response = await client.graphs.removeRelationship({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    relationshipId: "123e4567-e89b-12d3-a456-426614174000",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def remove_relationship_from_graph(
            id: UUID = Path(
                ...,
                description="The ID of the graph to remove the relationship from.",
            ),
            relationship_id: UUID = Path(
                ...,
                description="The ID of the relationship to remove from the graph.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Removes a relationship from the graph by its ID.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to remove a relationship from this graph.",
                    403,
                )

            if not await self.services["management"].has_relationship_access(
                auth_user, relationship_id
            ):
                raise R2RException(
                    "You do not have permission to remove this relationship from the graph.",
                    403,
                )

            await self.services["kg"].remove_relationship_from_graph(
                graph_id=id, relationship_id=relationship_id
            )

            return GenericBooleanResponse(success=True)

        ### Add and remove document from graph
        @self.router.post(
            "/graphs/{id}/documents/{document_id}",
            summary="Add a document to the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.graphs.add_document(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                document_id="123e4567-e89b-12d3-a456-426614174000"
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
                                const response = await client.graphs.addDocument({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    documentId: "123e4567-e89b-12d3-a456-426614174000",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def add_document_to_graph(
            id: UUID = Path(
                ...,
                description="The ID of the graph to add the entity to.",
            ),
            document_id: UUID = Path(
                ..., description="The ID of the document to add to the graph."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Adds a document to the graph by its ID.

            This endpoint adds all entities and relationships from the document to the graph.

            You need to run '/documents/{id}/entities_and_relationships' first to get the entities and relationships.

            The endpoints returns an error if there are no entities and relationships extractions present for the document.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    message="You do not have permission to add this document to the graph.",
                    status_code=403,
                )

            if not await self.services["management"].has_document_access(
                auth_user, document_id
            ):
                raise R2RException(
                    message="You do not have permission to add this document to the graph.",
                    status_code=403,
                )

            await self.services["kg"].add_documents_to_graph(
                graph_id=id,
                document_ids=[document_id],
            )

            return GenericBooleanResponse(success=True)

        @self.router.delete(
            "/graphs/{id}/documents/{document_id}",
            summary="Remove a document from the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.graphs.remove_document(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                document_id="123e4567-e89b-12d3-a456-426614174000"
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
                                const response = await client.graphs.removeDocument({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    documentId: "123e4567-e89b-12d3-a456-426614174000",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def remove_document_from_graph(
            id: UUID = Path(
                ...,
                description="The ID of the graph to remove the entity from.",
            ),
            document_id: UUID = Path(
                ...,
                description="The ID of the document to remove from the graph.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Removes a document from the graph by its ID.

            This endpoint removes all entities and relationships from the document in the graph.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    message="You do not have permission to remove this document from the graph.",
                    status_code=403,
                )

            if not await self.services["management"].has_document_access(
                auth_user, document_id
            ):
                raise R2RException(
                    message="You do not have permission to remove this document from the graph.",
                    status_code=403,
                )

            await self.services["kg"].remove_documents_from_graph(
                graph_id=id,
                document_ids=[document_id],
            )

            return GenericBooleanResponse(success=True)

        @self.router.post(
            "/graphs/{id}/collections/{collection_id}",
            summary="Add a collection to the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.graphs.add_collection(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                collection_id="123e4567-e89b-12d3-a456-426614174000"
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
                                const response = await client.graphs.addCollection({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    collectionId: "123e4567-e89b-12d3-a456-426614174000",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def add_collection_to_graph(
            id: UUID = Path(
                ...,
                description="The ID of the graph to add the entity to.",
            ),
            collection_id: UUID = Path(
                ...,
                description="The ID of the collection to add to the graph.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGenericMessageResponse:
            """
            Adds a collection to the graph by its ID.

            This endpoint adds all entities and relationships from all documents in the collection to the graph.

            The endpoints returns an error if there are no entities and relationships extractions present for any of the documents in the collection.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    message="You do not have permission to add this collection to the graph.",
                    status_code=403,
                )

            if not await self.services["management"].has_collection_access(
                auth_user, collection_id
            ):
                raise R2RException(
                    message="You do not have permission to add this collection to the graph.",
                    status_code=403,
                )

            return await self.services["kg"].add_collection_to_graph(
                graph_id=id,
                collection_id=collection_id,
            )

        @self.router.delete(
            "/graphs/{id}/collections/{collection_id}",
            summary="Remove a collection from the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.graphs.remove_collection(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                collection_id="123e4567-e89b-12d3-a456-426614174000"
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
                                const response = await client.graphs.removeCollection({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    collectionId: "123e4567-e89b-12d3-a456-426614174000",
                                });
                            }

                            main();
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def remove_collection_from_graph(
            id: UUID = Path(
                ...,
                description="The ID of the graph to remove the entity from.",
            ),
            collection_id: UUID = Path(
                ...,
                description="The ID of the collection to remove from the graph.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Removes a document from the graph by its ID.

            This endpoint removes all entities and relationships from all documents in the collection in the graph.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    message="You do not have permission to remove this collection from the graph.",
                    status_code=403,
                )

            if not await self.services["management"].has_collection_access(
                auth_user, collection_id
            ):
                raise R2RException(
                    message="You do not have permission to remove this collection from the graph.",
                    status_code=403,
                )

            await self.services["kg"].remove_collection_from_graph(
                graph_id=id,
                collection_id=collection_id,
            )

            return GenericBooleanResponse(success=True)
