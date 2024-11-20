import logging
import textwrap
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query

from core.base import R2RException, RunType
from core.base.abstractions import DataLevel, KGRunType
from core.base.abstractions import Community, Entity, Relationship, Graph

from core.base.api.models import (
    GenericMessageResponse,
    WrappedGenericMessageResponse,
    WrappedKGCreationResponse,
    WrappedEntityResponse,
    WrappedEntitiesResponse,
    WrappedRelationshipResponse,
    WrappedRelationshipsResponse,
    WrappedCommunityResponse,
    WrappedCommunitiesResponse,
    WrappedKGEntityDeduplicationResponse,
    WrappedKGEnrichmentResponse,
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

from core.base.abstractions import DocumentResponse, DocumentType

from .base_router import BaseRouterV3

from fastapi import Request

from shared.utils.base_utils import generate_entity_document_id

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
                    {
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
                            )"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_empty_graph(
            auth_user=Depends(self.providers.auth.auth_wrapper),
            graph: Graph = Body(...),
        ):
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
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can create graphs", 403)

            graph_id = await self.services["kg"].create_new_graph(graph)

            return {
                "id": graph_id,
                "message": "An empty graph object created successfully",
            }

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
        ):
            """
            Retrieves detailed information about a specific graph by ID.

            Returns a graph object containing:
            - Creation metadata: status, timestamp, creator
            - Enrichment metadata: status, timestamp, last enrichment run
            - Graph statistics:
                - Total entity count and types
                - Total relationship count and types
                - Number of communities and hierarchy levels
            - Graph settings:
                - Entity extraction settings
                - Relationship extraction settings
                - Community detection settings
                - Current prompt configurations

            The graph details can be used to:
            - Monitor graph processing status
            - Get graph size and composition metrics
            - View and validate graph configuration
            - Track enrichment progress
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can view graph status", 403
                )

            return (
                await self.services["kg"].get_graphs(
                    graph_id=id, offset=0, limit=1
                )
            )["results"][0]

        @self.router.get(
            "/graphs",
            summary="List graphs",
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
        async def get_graphs(
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Lists all graphs in the system with pagination support.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can view graph status", 403
                )

            results = await self.services["kg"].get_graphs(
                offset=offset, limit=limit, graph_id=None
            )
            return results["results"], {
                "total_entries": results["total_entries"]
            }

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
        ):
            """
            Deletes a graph and all its associated data.

            This endpoint permanently removes the specified graph along with all entities and relationships that belong to only this graph.

            Entities and relationships extracted from documents are not deleted and must be deleted separately using the /entities and /relationships endpoints.
            """
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can delete graphs", 403)

            id = await self.services["kg"].delete_graph_v3(
                id=id
            )
            # FIXME: Can we sync this with the deletion response from other routes? Those return a boolean.
            return {"message": "Graph deleted successfully", "id": id}  # type: ignore

        # update graph
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
                ]
            },
        )
        @self.base_endpoint
        async def update_graph(
            id: UUID = Path(...),
            graph: Graph = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Updates an existing graph's metadata and settings.

            This endpoint allows you to modify:
            - Basic metadata: name, description, tags
            - Graph settings:
                - Entity extraction settings
                - Relationship extraction settings 
                - Community detection settings
                - Prompt configurations
            
            The graph ID must match between the URL path and request body (if provided in body).
            """
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can update graphs", 403)

            if graph.id is None:
                graph.id = id
            else:
                if graph.id != id:
                    raise R2RException(
                        "Graph ID in path and body do not match", 400
                    )

            return {
                "id": (await self.services["kg"].update_graph(graph))["id"],
                "message": "Graph updated successfully",
            }

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
            "/graphs/{id}/documents",
            summary="Extract entities and relationships from a document and add them to the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.extract_entities_and_relationships(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
                            )
                            """
                        ),
                    },
                ],
                "operationId": "documents_extract_entities_and_relationships_v3_documents__id__entities_and_relationships_post_documents",
            },
        )
        @self.base_endpoint
        async def extract_entities_and_relationships(
            id: UUID = Path(
                ...,
                description="The ID of the document to extract entities and relationships from.",
            ),
            run_type: KGRunType = Query(
                default=KGRunType.ESTIMATE,
                description="Whether to return an estimate of the creation cost or to actually extract the entities and relationships.",
            ),
            settings: Optional[KGCreationSettings] = Body(
                default=None,
                description="Settings for the entities and relationships extraction process.",
            ),
            run_with_orchestration: Optional[bool] = Query(
                default=True,
                description="Whether to run the entities and relationships extraction process with orchestration.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGCreationResponse:  # type: ignore
            """
            Extracts entities and relationships from a document and adds them to the graph.

            The entities and relationships extraction process involves:
            1. Parsing documents into semantic chunks
            2. Extracting entities and relationships using LLMs

            If the entities and relationships were already extracted for the document, they will not be extracted again and the existing entities and relationships will be added to the graph.
            """

            settings = settings.dict() if settings else None  # type: ignore
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            # If no run type is provided, default to estimate
            if not run_type:
                run_type = KGRunType.ESTIMATE

            # Apply runtime settings overrides
            server_kg_creation_settings = (
                self.providers.database.config.kg_creation_settings
            )

            if settings:
                server_kg_creation_settings = update_settings_from_dict(
                    server_settings=server_kg_creation_settings,
                    settings_dict=settings,  # type: ignore
                )

            # If the run type is estimate, return an estimate of the creation cost
            if run_type is KGRunType.ESTIMATE:
                return {  # type: ignore
                    "message": "Estimate retrieved successfully",
                    "task_id": None,
                    "id": id,
                    "estimate": await self.services[
                        "kg"
                    ].get_creation_estimate(
                        document_id=id,
                        kg_creation_settings=server_kg_creation_settings,
                    ),
                }
            else:
                # Otherwise, create the graph
                if run_with_orchestration:
                    workflow_input = {
                        "document_id": str(id),
                        "kg_creation_settings": server_kg_creation_settings.model_dump_json(),
                        "user": auth_user.json(),
                    }

                    return await self.orchestration_provider.run_workflow(  # type: ignore
                        "create-graph", {"request": workflow_input}, {}
                    )
                else:
                    from core.main.orchestration import simple_kg_factory

                    logger.info("Running create-graph without orchestration.")
                    simple_kg = simple_kg_factory(self.services["kg"])
                    await simple_kg["create-graph"](workflow_input)  # type: ignore
                    return {  # type: ignore
                        "message": "Graph created successfully.",
                        "task_id": None,
                    }

        

        @self.router.post(
            "/graphs/{id}/entities",
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
                            result = client.graphs.add_entity(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_ids=[
                                "123e4567-e89b-12d3-a456-426614174000",
                                "123e4567-e89b-12d3-a456-426614174001",
                            ])
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def add_entity_to_graph(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to add the entity to.",
            ),
            entity_ids: list[UUID] = Body(
                ..., description="The IDs of the entities to add to the graph."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Adds a list of entities to the graph by their IDs.
            """
            return await self.services["kg"].documents.graph_handler.entities.add_to_graph(id, entity_ids)

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
                ],
            },
        )
        @self.base_endpoint
        async def remove_entity_from_graph(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to remove the entity from.",
            ),
            entity_id: UUID = Path(
                ..., description="The ID of the entity to remove from the graph."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Removes an entity from the graph by its ID.
            """
            return await self.services["kg"].documents.graph_handler.entities.remove_from_graph(id, [entity_id])


        @self.router.post(
            "/graphs/{id}/relationships",
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
                            result = client.graphs.add_relationship(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_ids=[
                                "123e4567-e89b-12d3-a456-426614174000",
                                "123e4567-e89b-12d3-a456-426614174001",
                            ])
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def add_relationship_to_graph(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to add the relationship to.",
            ),
            relationship_ids: list[UUID] = Body(
                ..., description="The IDs of the relationships to add to the graph."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Adds a list of relationships to the graph by their IDs.
            """
            return await self.services["kg"].documents.graph_handler.relationships.add_to_graph(id, relationship_ids)
        


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
                            result = client.graphs.remove_relationships(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_ids=[
                                "123e4567-e89b-12d3-a456-426614174000",
                                "123e4567-e89b-12d3-a456-426614174001",
                            ])
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def remove_relationship_from_graph(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to remove the relationship from.",
            ),
            relationship_id: UUID = Path(
                ..., description="The ID of the relationship to remove from the graph."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Removes a relationship from the graph by its ID.
            """
            return await self.services["kg"].documents.graph_handler.relationships.remove_from_graph(id, [relationship_id])



        @self.router.post(
            "/graphs/{id}/communities",
            summary="Add communities to the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.graphs.add_communities(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", community_ids=[
                                "123e4567-e89b-12d3-a456-426614174000",
                                "123e4567-e89b-12d3-a456-426614174001",
                            ])
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def add_communities_to_graph(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to add the communities to.",
            ),
            community_ids: list[UUID] = Body(
                ..., description="The IDs of the communities to add to the graph."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Adds a list of communities to the graph by their IDs.
            """
            return await self.services["kg"].documents.graph_handler.communities.add_to_graph(id, community_ids)
        


        @self.router.delete(
            "/graphs/{id}/communities/{community_id}",
            summary="Remove a community from the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient
                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)
                            result = client.graphs.remove_communities(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", community_ids=[
                                "123e4567-e89b-12d3-a456-426614174000",
                                "123e4567-e89b-12d3-a456-426614174001",
                            ])
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def remove_community_from_graph(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to remove the community from.",
            ),
            community_id: UUID = Path(
                ..., description="The ID of the community to remove from the graph."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Removes a community from the graph by its ID.
            """
            return await self.services["kg"].documents.graph_handler.communities.remove_from_graph(id, [community_id])

