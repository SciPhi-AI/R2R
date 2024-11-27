import logging
import textwrap
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query

from core.base import R2RException, RunType
from core.base.abstractions import (
    KGRunType,
)
from core.base.api.models import (
    GenericBooleanResponse,
    WrappedBooleanResponse,
    WrappedCommunitiesResponse,
    WrappedCommunityResponse,
    WrappedEntitiesResponse,
    WrappedEntityResponse,
    WrappedGraphResponse,
    WrappedGraphsResponse,
    WrappedKGEnrichmentResponse,
    WrappedKGTunePromptResponse,
    WrappedRelationshipResponse,
    WrappedRelationshipsResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from core.utils import (
    generate_default_user_collection_id,
    update_settings_from_dict,
)

from .base_router import BaseRouterV3

logger = logging.getLogger()


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

    async def _deduplicate_entities(
        self,
        collection_id: UUID,
        settings,
        run_type: Optional[KGRunType] = KGRunType.ESTIMATE,
        run_with_orchestration: bool = True,
        auth_user=None,
    ):
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
                collection_id, server_settings
            )

        workflow_input = {
            "graph_id": str(collection_id),
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

    async def _get_collection_id(
        self, collection_id: Optional[UUID], auth_user
    ) -> UUID:
        """Helper method to get collection ID, using default if none provided"""
        if collection_id is None:
            return generate_default_user_collection_id(auth_user.id)
        return collection_id

    def _setup_routes(self):
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

                            result = client.graphs.list()
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

            graph_uuids = [UUID(graph_id) for graph_id in collection_ids]

            list_graphs_response = await self.services["kg"].list_graphs(
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
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
            collection_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGraphResponse:
            """
            Retrieves detailed information about a specific graph by ID.
            """
            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.graph_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            list_graphs_response = await self.services["kg"].list_graphs(
                # user_ids=None,
                graph_ids=[collection_id],
                offset=0,
                limit=1,
            )
            return list_graphs_response["results"][0]

        @self.router.post(
            "/graphs/{collection_id}/reset",
            summary="Reset a graph back to the initial state.",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.reset(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
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
                                const response = await client.graphs.reset({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/reset" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def reset(
            collection_id: UUID = Path(...),
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
            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.graph_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            await self.services["kg"].delete_graph_v3(id=collection_id)
            return GenericBooleanResponse(success=True)  # type: ignore

        # update graph
        @self.router.post(
            "/graphs/{collection_id}",
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
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
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
                                    collection_id: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Update an existing graphs's configuration.

            This endpoint allows updating the name and description of an existing collection.
            The user must have appropriate permissions to modify the collection.
            """
            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.collection_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified collection.",
                    403,
                )

            return await self.services["kg"].update_graph(  # type: ignore
                collection_id,
                name=name,
                description=description,
            )

        @self.router.get(
            "/graphs/{collection_id}/entities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.get_entities(collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7")
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
                                const response = await client.graphs.get_entities({
                                    collection_id: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedEntitiesResponse:
            """Lists all entities in the graph with pagination support."""
            # return await self.services["kg"].get_entities(
            #     id, offset, limit, auth_user
            # )
            entities, count = (
                await self.providers.database.graph_handler.get_entities(
                    collection_id, offset, limit
                )
            )

            return entities, {  # type: ignore
                "total_entries": count,
            }

        @self.router.post("/graphs/{collection_id}/entities")
        @self.base_endpoint
        async def create_entity(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to add the entity to.",
            ),
            name: str = Body(
                ..., description="The name of the entity to create."
            ),
            description: Optional[str] = Body(
                None, description="The description of the entity to create."
            ),
            category: Optional[str] = Body(
                None, description="The category of the entity to create."
            ),
            metadata: Optional[dict] = Body(
                None, description="The metadata of the entity to create."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedEntityResponse:
            """Creates a new entity in the graph."""
            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.graph_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to this graph.",
                    403,
                )

            return await self.services["kg"].create_entity(
                name=name,
                description=description,
                parent_id=collection_id,
                category=category,
                metadata=metadata,
            )

        @self.router.post("/graphs/{collection_id}/relationships")
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
            description: Optional[str] = Body(
                None,
                description="The description of the relationship to create.",
            ),
            weight: Optional[float] = Body(
                None, description="The weight of the relationship to create."
            ),
            metadata: Optional[dict] = Body(
                None, description="The metadata of the relationship to create."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRelationshipResponse:
            """Creates a new relationship in the graph."""
            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.graph_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to this graph.",
                    403,
                )

            return await self.services["kg"].create_relationship(
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

        @self.router.get(
            "/graphs/{collection_id}/entities/{entity_id}",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.get_entity(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                entity_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
                                const response = await client.graphs.get_entity({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    entityId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
        async def get_entity(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph containing the entity.",
            ),
            entity_id: UUID = Path(
                ..., description="The ID of the entity to retrieve."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedEntityResponse:
            """Retrieves a specific entity by its ID."""
            # Note: The original was missing implementation, so assuming similar pattern to relationships
            result = await self.providers.database.graph_handler.entities.get(
                collection_id, "graph", entity_ids=[entity_id]
            )
            if len(result) == 0 or len(result[0]) == 0:
                raise R2RException("Entity not found", 404)
            return result[0][0]

        @self.router.post("/graphs/{collection_id}/entities/{entity_id}")
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
            category: Optional[str] = Body(
                None, description="The updated category of the entity."
            ),
            description: Optional[str] = Body(
                None, description="The updated description of the entity."
            ),
            metadata: Optional[dict] = Body(
                None, description="The updated metadata of the entity."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedEntityResponse:
            """Updates an existing entity in the graph."""
            entity.id = entity_id
            entity.parent_id = (
                entity.parent_id or collection_id
            )  # Set parent ID to graph ID
            results = await self.providers.database.graph_handler.entities.update(
                [entity],
                store_type="graph",
                # id, entity_id, entity, auth_user
            )
            print("results = ", results)
            return entity

        @self.router.delete(
            "/graphs/{collection_id}/entities/{entity_id}",
            summary="Remove an entity",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.remove_entity(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                entity_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
                                const response = await client.graphs.removeEntity({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    entityId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
        async def delete_entity(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to remove the entity from.",
            ),
            entity_id: UUID = Path(
                ...,
                description="The ID of the entity to remove from the graph.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """Removes an entity from the graph."""
            await self.providers.database.graph_handler.entities.delete(
                collection_id, [entity_id], "graph"
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.get(
            "/graphs/{collection_id}/relationships",
            description="Lists all relationships in the graph with pagination support.",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.list_relationships(collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7")
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
                                const response = await client.graphs.listRelationships({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRelationshipsResponse:
            """
            Lists all relationships in the graph with pagination support.
            """
            # Permission check
            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.graph_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to this graph.",
                    403,
                )

            relationships, count = (
                await self.providers.database.graph_handler.relationships.get(
                    parent_id=collection_id,
                    store_type="graph",
                    offset=offset,
                    limit=limit,
                )
            )

            return relationships, {  # type: ignore
                "total_entries": count,
            }

        @self.router.get(
            "/graphs/{collection_id}/relationships/{relationship_id}",
            description="Retrieves a specific relationship by its ID.",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.get_relationship(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                relationship_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
                                const response = await client.graphs.getRelationship({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    relationshipId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
        async def get_relationship(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph containing the relationship.",
            ),
            relationship_id: UUID = Path(
                ..., description="The ID of the relationship to retrieve."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRelationshipResponse:
            """Retrieves a specific relationship by its ID."""
            results = (
                await self.providers.database.graph_handler.relationships.get(
                    collection_id, "graph", relationship_ids=[relationship_id]
                )
            )
            if len(results) == 0 or len(results[0]) == 0:
                raise R2RException("Relationship not found", 404)
            return results[0][0]

        @self.router.post(
            "/graphs/{collection_id}/relationships/{relationship_id}"
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
            predicate: Optional[str] = Body(
                ..., description="The updated predicate of the relationship."
            ),
            object: Optional[str] = Body(
                ..., description="The updated object of the relationship."
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRelationshipResponse:
            """Updates an existing relationship in the graph."""
            relationship.id = relationship_id
            relationship.parent_id = relationship.parent_id or collection_id
            return await self.providers.database.graph_handler.relationships.update(
                [relationship], "graph"
            )

        @self.router.delete(
            "/graphs/{collection_id}/relationships/{relationship_id}",
            description="Removes a relationship from the graph.",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.delete_relationship(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                relationship_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
                                const response = await client.graphs.deleteRelationship({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    relationshipId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
        async def delete_relationship(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to remove the relationship from.",
            ),
            relationship_id: UUID = Path(
                ...,
                description="The ID of the relationship to remove from the graph.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """Removes a relationship from the graph."""
            # return await self.services[
            #     "kg"
            # ].documents.graph_handler.relationships.remove_from_graph(
            #     id, relationship_id, auth_user
            # )
            await self.providers.database.graph_handler.relationships.delete(
                collection_id, [relationship_id], "graph"
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/graphs/{collection_id}/communities/build",
            summary="Builds the graph communities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.communities.build(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
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
                                const response = await client.graphs.communities.build({
                                    collectionId: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
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
        async def create_communities(
            collection_id: UUID = Path(...),
            settings: Optional[dict] = Body(None),
            run_type: Optional[KGRunType] = Query(
                description="Run type for the graph creation process.",
            ),
            run_with_orchestration: bool = Query(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGEnrichmentResponse:
            """
            Creates communities in the graph by analyzing entity relationships and similarities.

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

            return await self._create_communities(
                graph_id=collection_id,
                settings=settings,
                run_type=run_type,
                run_with_orchestration=run_with_orchestration,
                auth_user=auth_user,
            )

        @self.router.post(
            "/graphs/{collection_id}/communities",
            summary="Create a new community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.communities.create(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", communities=[community1, community2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_communities(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to create the community in.",
            ),
            name: str = Body(..., description="The name of the community"),
            summary: str = Body(..., description="A summary of the community"),
            findings: Optional[list[str]] = Body(
                default=[], description="Findings about the community"
            ),
            level: Optional[int] = Body(
                default=0,
                ge=0,
                le=100,
                description="The level of the community",
            ),
            rating: Optional[float] = Body(
                default=5, ge=1, le=10, description="Rating between 1 and 10"
            ),
            rating_explanation: Optional[str] = Body(
                default="", description="Explanation for the rating"
            ),
            attributes: Optional[dict] = Body(
                default=None, description="Attributes for the community"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Creates a new community in the graph.

            While communities are typically built automatically via the /graphs/{id}/communities/build endpoint,
            this endpoint allows you to manually create your own communities. This can be useful when you want to:

            - Define custom groupings of entities based on domain knowledge
            - Add communities that weren't detected by the automatic process
            - Create hierarchical organization structures
            - Tag groups of entities with specific metadata

            The created communities will be integrated with any existing automatically detected communities
            in the graph's community structure.
            """
            return await self.services["kg"].create_community_v3(
                graph_id=collection_id,
                name=name,
                summary=summary,
                findings=findings,
                rating=rating,
                rating_explanation=rating_explanation,
                level=level,
                attributes=attributes,
                auth_user=auth_user,
            )

        @self.router.get(
            "/graphs/{collection_id}/communities",
            summary="List communities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.list_communities(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
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
                                const response = await client.graphs.listCommunities({
                                    collectionId: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCommunitiesResponse:
            """
            Lists all communities in the graph with pagination support.

            By default, all attributes are returned, but this can be limited using the `attributes` parameter.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            communities, count = await self.services[
                "kg"
            ].providers.database.graph_handler.communities.get(
                graph_id=collection_id,
                offset=offset,
                limit=limit,
                auth_user=auth_user,
            )

            return communities, {  # type: ignore
                "total_entries": count,
            }

        @self.router.get(
            "/graphs/{collection_id}/communities/{community_id}",
            summary="Retrieve a community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.get_community(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
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
                                const response = await client.graphs.getCommunity({
                                    collectionId: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
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
        async def get_community(
            collection_id: UUID = Path(
                ...,
                description="The ID of the collection to get communities for.",
            ),
            community_id: UUID = Path(
                ...,
                description="The ID of the community to get.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCommunityResponse:
            """
            Retrieves a specific community by its ID.

            By default, all attributes are returned, but this can be limited using the `attributes` parameter.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            return await self.services[
                "kg"
            ].providers.database.graph_handler.communities.get(
                graph_id=collection_id,
                community_id=community_id,
                auth_user=auth_user,
                offset=0,
                limit=1,
            )

        @self.router.delete(
            "/graphs/{collection_id}/communities/{community_id}",
            summary="Delete a community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.delete_community(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                community_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
                                const response = await client.graphs.deleteCommunity({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    communityId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
        async def delete_community(
            collection_id: UUID = Path(
                ...,
                description="The collection ID corresponding to the graph to delete the community from.",
            ),
            community_id: UUID = Path(
                ...,
                description="The ID of the community to delete.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )
            await self.services["kg"].delete_community_v3(
                graph_id=collection_id,
                community_id=community_id,
                auth_user=auth_user,
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.post(
            "/graphs/{collection_id}/communities/{community_id}",
            summary="Update community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.update_community(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                community_update={
                                    "metadata": {
                                        "topic": "Technology",
                                        "description": "Tech companies and products"
                                    }
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
                            """
                        ),
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
            rating: Optional[float] = Body(None),
            rating_explanation: Optional[str] = Body(None),
            level: Optional[int] = Body(None),
            attributes: Optional[dict] = Body(None),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCommunityResponse:
            """
            Updates an existing community's metadata and properties.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can update communities", 403
                )

            return await self.services["kg"].update_community_v3(
                id=collection_id,
                community_id=community_id,
                name=name,
                summary=summary,
                findings=findings,
                rating=rating,
                rating_explanation=rating_explanation,
                level=level,
                attributes=attributes,
                auth_user=auth_user,
            )

        @self.router.post(
            "/graphs/{collection_id}/pull",
            summary="Pull latest entities to the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.pull(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )"""
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            async function main() {
                                const response = await client.graphs.pull({
                                    collection_id: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
        async def pull(
            collection_id: UUID = Path(
                ..., description="The ID of the graph to initialize."
            ),
            # document_ids: list[UUID] = Body(
            #     ..., description="List of document IDs to add to the graph."
            # ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Adds documents to a graph by copying their entities and relationships.

            This endpoint:
            1. Copies document entities to the graph_entity table
            2. Copies document relationships to the graph_relationship table
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
            # Check user permissions for graph
            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.graph_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified graph.",
                    403,
                )
            list_graphs_response = await self.services["kg"].list_graphs(
                # user_ids=None,
                graph_ids=[collection_id],
                offset=0,
                limit=1,
            )
            if len(list_graphs_response["results"]) == 0:
                raise R2RException("Graph not found", 404)
            collection_id = list_graphs_response["results"][0].collection_id
            documents = []
            document_req = (
                await self.providers.database.collections_handler.documents_in_collection(
                    collection_id, offset=0, limit=100
                )
            )["results"]
            documents.extend(document_req)
            while len(document_req) == 100:
                document_req = (
                    await self.providers.database.collections_handler.documents_in_collection(
                        collection_id, offset=len(documents), limit=100
                    )
                )["results"]
                documents.extend(document_req)

            success = False

            for document in documents:
                if (
                    not auth_user.is_superuser
                    and document.id
                    not in auth_user.document_ids  # TODO - extend to include checks on collections
                ):
                    raise R2RException(
                        f"The currently authenticated user does not have access to document {document.id}",
                        403,
                    )
                entities = (
                    await self.providers.database.graph_handler.entities.get(
                        document.id, store_type="document"
                    )
                )
                has_document = (
                    await self.providers.database.graph_handler.has_document(
                        collection_id, document.id
                    )
                )
                if has_document:
                    logger.info(
                        f"Document {document.id} is already in graph {collection_id}, skipping"
                    )
                    continue
                if len(entities[0]) == 0:
                    logger.warning(
                        f"Document {document.id} has no entities, extraction may not have been called"
                    )
                    continue

                success = (
                    await self.providers.database.graph_handler.add_documents(
                        id=collection_id,
                        document_ids=[
                            document.id
                        ],  # [doc.id for doc in documents]
                    )
                )
            if not success:
                logger.warning(
                    f"No documents were added to graph {collection_id}, marking as failed."
                )

            return GenericBooleanResponse(success=success)  # type: ignore

        @self.router.delete(
            "/graphs/{collection_id}/documents/{document_id}",
            summary="Remove document from graph",
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
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                document_id="f98db41a-5555-4444-3333-222222222222"
                            )"""
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            async function main() {
                                const response = await client.graphs.removeDocument({
                                    collectionId: "d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    documentId: "f98db41a-5555-4444-3333-222222222222"
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
        async def remove_document(
            collection_id: UUID = Path(
                ...,
                description="The ID of the graph to remove the document from.",
            ),
            document_id: UUID = Path(
                ..., description="The ID of the document to remove."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Removes a document from a graph and removes any associated entities

            This endpoint:
            1. Removes the document ID from the graph's document_ids array
            2. Optionally deletes the document's copied entities and relationships

            The user must have access to both the graph and the document being removed.
            """
            # Check user permissions for graph
            if (
                not auth_user.is_superuser
                and collection_id not in auth_user.graph_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified graph.",
                    403,
                )

            # Check user permissions for document
            if (
                not auth_user.is_superuser
                and document_id not in auth_user.document_ids
            ):
                raise R2RException(
                    "The currently authenticated user does not have access to the specified document.",
                    403,
                )

            success = (
                await self.providers.database.graph_handler.remove_documents(
                    id=collection_id,
                    document_ids=[document_id],  # , delete_data=delete_data
                )
            )

            return GenericBooleanResponse(success=success)  # type: ignore
