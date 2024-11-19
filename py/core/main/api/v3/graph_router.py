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
            """Creates an empty graph for a collection."""
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can create graphs", 403)

            graph_id = await self.services["kg"].create_new_graph(graph)

            return {
                "id": graph_id,
                "message": "An empty graph object created successfully",
            }

        @self.router.get(
            "/graphs/{id}",
            summary="Get graph information",
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
            Gets the information about a graph.

            Returns information about:
            - Creation status and timestamp
            - Enrichment status and timestamp
            - Entity and relationship counts
            - Community statistics
            - Current settings
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
            summary="Get graph information",
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
            Gets the information about a graph.

            Returns information about:
            - Creation status and timestamp
            - Enrichment status and timestamp
            - Entity and relationship counts
            - Community statistics
            - Current settings
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
            cascade: bool = Query(False),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Deletes the graph and associated entities and relationships.
            """
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can delete graphs", 403)

            if cascade:
                raise NotImplementedError(
                    "Cascade deletion not implemented. Please delete document level entities and relationships using the document delete endpoints."
                )

            id = await self.services["kg"].delete_graph_v3(
                id=id, cascade=cascade
            )
            # FIXME: Can we sync this with the deletion response from other routes? Those return a boolean.
            return {"message": "Graph deleted successfully", "id": id}  # type: ignore

        # update graph
        @self.router.post(
            "/graphs/{id}",
            summary="Update the graph object",
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
            Updates the graph object.

            The graph object can be updated to change the name, description, settings and other attributes.
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
            "/graphs/{id}/add_objects",
            summary="Add entities and relationships to a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.add_objects(
                                id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                object_type="entities",
                                object_ids=[
                                    "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    "9fbe403b-c11c-5aae-8ade-ef22980c3ad2"
                                ]
                            )"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def add_data(
            id: UUID = Path(...),
            object_type: GraphObjectType = Body(...),
            object_ids: list[UUID] = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Adds entities and relationships to a graph.

            If the object type is documents or collections, then all entities and relationships that are present in the documents or collections will be added to the graph.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can add data to graphs", 403
                )

            if object_type == GraphObjectType.DOCUMENTS:
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.add_documents(
                    id=id, document_ids=object_ids
                )
            elif object_type == GraphObjectType.COLLECTIONS:
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.add_collections(
                    id=id, collection_ids=object_ids
                )
            elif object_type == GraphObjectType.ENTITIES:
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.add_entities_v3(
                    id=id, entity_ids=object_ids
                )
            elif object_type == GraphObjectType.RELATIONSHIPS:
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.add_relationships_v3(
                    id=id, relationship_ids=object_ids
                )
            else:
                raise R2RException("Invalid data type", 400)

        # remove data
        @self.router.delete(
            "/graphs/{id}/remove_objects",
            summary="Remove entities and relationships from a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.remove_objects(
                                id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                object_type="entities",
                                object_ids=[
                                    "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    "9fbe403b-c11c-5aae-8ade-ef22980c3ad2"
                                ]
                            )"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def remove_data(
            id: UUID = Path(...),
            object_type: GraphObjectType = Body(...),
            object_ids: list[UUID] = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Removes entities and relationships from a graph.

            If the object type is documents or collections, then all entities and relationships that are present in the documents or collections will be removed from the graph.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can remove data from graphs", 403
                )

            if object_type == GraphObjectType.DOCUMENTS:
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.remove_documents(
                    id=id, document_ids=object_ids
                )
            elif object_type == GraphObjectType.COLLECTIONS:
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.remove_collections(
                    id=id, collection_ids=object_ids
                )
            elif object_type == GraphObjectType.ENTITIES:
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.remove_entities(
                    id=id, entity_ids=object_ids
                )
            elif object_type == GraphObjectType.RELATIONSHIPS:
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.remove_relationships(
                    id=id, relationship_ids=object_ids
                )
            else:
                raise R2RException("Invalid data type", 400)

        @self.router.post(
            "/graphs/{collection_id}/tune-prompt",
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
            collection_id: UUID = Path(...),
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
                collection_id=collection_id,
                documents_offset=documents_offset,
                documents_limit=documents_limit,
                chunks_offset=chunks_offset,
                chunks_limit=chunks_limit,
            )

            return tuned_prompt  # type: ignore
