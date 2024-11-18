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
            "id": str(id),
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
   
    async def _create_communities(
        self,
        graph_id: UUID,
        settings,
        run_type: Optional[KGRunType] = KGRunType.ESTIMATE,
        run_with_orchestration: bool = True,
        auth_user=None,
    ) -> WrappedKGEnrichmentResponse:
        """Creates communities in the graph by analyzing entity relationships and similarities.

        Communities are created by:
        1. Builds similarity graph between entities
        2. Applies community detection algorithm (e.g. Leiden)
        3. Creates hierarchical community levels
        4. Generates summaries and insights for each community
        """
        if not auth_user.is_superuser:
            raise R2RException(
                "Only superusers can create communities", 403
            )

        # Apply runtime settings overrides
        server_kg_enrichment_settings = (
            self.providers.database.config.kg_enrichment_settings
        )
        if settings:
            server_kg_enrichment_settings = update_settings_from_dict(
                server_kg_enrichment_settings, settings
            )

        workflow_input = {
            "graph_id": str(graph_id),
            "kg_enrichment_settings": server_kg_enrichment_settings.model_dump_json(),
            "user": auth_user.model_dump_json(),
        }

        if not run_type:
            run_type = KGRunType.ESTIMATE

        # If the run type is estimate, return an estimate of the enrichment cost
        if run_type is KGRunType.ESTIMATE:
            return await self.services["kg"].get_enrichment_estimate(
                id, server_kg_enrichment_settings
            )

        else:
            if run_with_orchestration:
                return await self.orchestration_provider.run_workflow(  # type: ignore
                    "enrich-graph", {"request": workflow_input}, {}
                )
            else:
                from core.main.orchestration import simple_kg_factory

                simple_kg = simple_kg_factory(self.services["kg"])
                await simple_kg["enrich-graph"](workflow_input)
                return {  # type: ignore
                    "message": "Communities created successfully.",
                    "task_id": None,
                }

    def _setup_routes(self):

        # create graph new endpoint
        @self.router.post(
            "/documents/{id}/graphs/{run_type}",
        )
        @self.base_endpoint
        async def create_graph(
            id: UUID = Path(
                ...,
                description="The ID of the document to create a graph for.",
            ),
            run_type: KGRunType = Path(
                description="Run type for the graph creation process.",
            ),
            settings: Optional[KGCreationSettings] = Body(
                default=None,
                description="Settings for the graph creation process.",
            ),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGCreationResponse:  # type: ignore
            """
            Creates a new knowledge graph by extracting entities and relationships from a document.
                The graph creation process involves:
                1. Parsing documents into semantic chunks
                2. Extracting entities and relationships using LLMs or NER
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
                return {
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

        # list entities
        @self.router.get(
            "/chunks/{id}/graphs/entities",
            summary="List entities for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.graphs.entities.list(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=100)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.get(
            "/documents/{id}/graphs/entities",
            summary="List entities for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.graphs.entities.list(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=100)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.get(
            "/graphs/{id}/entities",
            summary="List entities for a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.entities.list(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=100)
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_entities(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to retrieve entities for.",
            ),
            entity_names: Optional[list[str]] = Query(
                None,
                description="A list of entity names to filter the entities by.",
            ),
            entity_categories: Optional[list[str]] = Query(
                None,
                description="A list of entity categories to filter the entities by.",
            ),
            attributes: Optional[list[str]] = Query(
                None,
                description="A list of attributes to return. By default, all attributes are returned.",
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
            """
            Retrieves a list of entities associated with a specific chunk.

            Note that when entities are extracted, neighboring chunks are also processed together to extract entities.

            So, the entity returned here may not be in the same chunk as the one specified, but rather in a neighboring chunk (upto 2 chunks by default).
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            entities, count = await self.services["kg"].list_entities(
                level=self._get_path_level(request),
                id=id,
                offset=offset,
                limit=limit,
                entity_names=entity_names,
                entity_categories=entity_categories,
                attributes=attributes,
            )

            return entities, {  # type: ignore
                "total_entries": count,
            }

        @self.router.post(
            "/documents/{id}/graphs/entities",
            summary="Create entities for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.graphs.entities.create(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entities=[entity1, entity2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/graphs/{id}/entities",
            summary="Create entities for a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.entities.create(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entities=[entity1, entity2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_entities_v3(
            request: Request,
            id: UUID = Path(
                ..., description="The ID of the object to create entities for."
            ),
            entities: list[Entity] = Body(
                ..., description="The entities to create."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            # get entity level from path
            path = request.url.path
            if "/chunks/" in path:
                level = DataLevel.CHUNK
            elif "/documents/" in path:
                level = DataLevel.DOCUMENT
            else:
                level = DataLevel.GRAPH

            # set entity level if not set
            for entity in entities:
                if entity.level:
                    if entity.level != level:
                        raise R2RException(
                            "Entity level must match the path level.", 400
                        )
                else:
                    entity.level = level

            if level == DataLevel.DOCUMENT:
                for entity in entities:
                    if entity.document_id:
                        if entity.document_id != id:
                            raise R2RException(
                                "Entity document IDs must match the document ID or should be empty.",
                                400,
                            )
                    else:
                        entity.document_id = id

            elif level == DataLevel.GRAPH:
                for entity in entities:
                    entity.graph_id = id
                    entity.attributes = {
                        "manual_creation": True,
                    }

            res = await self.services["kg"].create_entities(
                entities=entities,
            )

            return res

        @self.router.post(
            "/documents/{id}/entities/{entity_id}",
            summary="Update an entity for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.graphs.entities.update(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000", entity=entity)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/graphs/{id}/entities/{entity_id}",
            summary="Update an entity for a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.entities.update(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000", entity=entity)
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_entity(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the chunk to update the entity for.",
            ),
            entity_id: UUID = Path(
                ..., description="The ID of the entity to update."
            ),
            entity: Entity = Body(..., description="The updated entity."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            if not entity.level:
                entity.level = self._get_path_level(request)
            else:
                if entity.level != self._get_path_level(request):
                    raise R2RException(
                        "Entity level must match the path level.", 400
                    )

            if entity.level == DataLevel.DOCUMENT:
                entity.document_id = id

            elif entity.level == DataLevel.GRAPH:
                entity.graph_id = id

            if not entity.id:
                entity.id = entity_id
            else:
                if entity.id != entity_id:
                    raise R2RException(
                        "Entity ID must match the entity ID or should be empty.",
                        400,
                    )

            return await self.services["kg"].update_entity_v3(
                entity=entity,
            )

        @self.router.delete(
            "/documents/{id}/graphs/entities/{entity_id}",
            summary="Delete an entity for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.graphs.entities.delete(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.delete(
            "/graphs/{id}/entities/{entity_id}",
            summary="Delete an entity for a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.gra phs.entities.delete(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_entity(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to delete the entity for.",
            ),
            entity_id: UUID = Path(
                ..., description="The ID of the entity to delete."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            return await self.services["kg"].delete_entity_v3(
                id=id,
                entity_id=entity_id,
                level=self._get_path_level(request),
            )

        @self.router.get(
            "/chunks/{id}/graphs/relationships",
            summary="List relationships for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.graphs.relationships.list(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.get(
            "/documents/{id}/graphs/relationships",
            summary="List relationships for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.graphs.relationships.list(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.get(
            "/graphs/{id}/relationships",
            summary="List relationships for a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.relationships.list(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_relationships(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the chunk to retrieve relationships for.",
            ),
            entity_names: Optional[list[str]] = Query(
                None,
                description="A list of entity names to filter the relationships by.",
            ),
            relationship_types: Optional[list[str]] = Query(
                None,
                description="A list of relationship types to filter the relationships by.",
            ),
            attributes: Optional[list[str]] = Query(
                None,
                description="A list of attributes to return. By default, all attributes are returned.",
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
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            relationships, count = await self.services[
                "kg"
            ].list_relationships_v3(
                level=self._get_path_level(request),
                id=id,
                entity_names=entity_names,
                relationship_types=relationship_types,
                attributes=attributes,
                offset=offset,
                limit=limit,
            )

            return relationships, {  # type: ignore
                "total_entries": count,
            }

        @self.router.post(
            "/documents/{id}/graphs/relationships",
            summary="Create relationships for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.graphs.relationships.create(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationships=[relationship1, relationship2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/graphs/{id}/relationships",
            summary="Create relationships for a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.relationships.create(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationships=[relationship1, relationship2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_relationships(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the chunk to create relationships for.",
            ),
            relationships: list[Relationship] = Body(
                ..., description="The relationships to create."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGCreationResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            relationships = await self.services["kg"].create_relationships_v3(
                id=id,
                relationships=relationships,
            )

            return {  # type: ignore
                "message": "Relationships created successfully.",
                "count": relationships,
            }

        @self.router.post(
            "/documents/{id}/relationships/{relationship_id}",
            summary="Update a relationship for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.relationships.update(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000", relationship=relationship)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/graphs/{id}/relationships/{relationship_id}",
            summary="Update a relationship for a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.relationships.update(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000", relationship=relationship)
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_relationship(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the chunk to update the relationship for.",
            ),
            relationship_id: UUID = Path(
                ..., description="The ID of the relationship to update."
            ),
            relationship: Relationship = Body(
                ..., description="The updated relationship."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            level = self._get_path_level(request)

            if not relationship.id:
                relationship.id = relationship_id
            else:
                if relationship.id != relationship_id:
                    raise ValueError(
                        "Relationship ID in path and body do not match"
                    )

            return await self.services["kg"].update_relationship_v3(
                relationship=relationship,
            )

        @self.router.delete(
            "/documents/{id}/graphs/relationships/{relationship_id}",
            summary="Delete a relationship for a document",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.graphs.relationships.delete(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.delete(
            "/graphs/{id}/relationships/{relationship_id}",
            summary="Delete a relationship for a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.documents.graphs.relationships.delete(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_relationship(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the chunk to delete the relationship for.",
            ),
            relationship_id: UUID = Path(
                ..., description="The ID of the relationship to delete."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            level = self._get_path_level(request)

            return await self.services["kg"].delete_relationship_v3(
                level=level,
                id=id,
                relationship_id=relationship_id,
            )

        ################### COMMUNITIES ###################

        @self.router.post(
            "/graphs/{id}/build/communities",
            summary="Build communities in the graph",
        )
        @self.base_endpoint
        async def create_communities(
            id: UUID = Path(...),
            settings: Optional[dict] = Body(None),
            run_type: Optional[KGRunType] = Body(
                default=None,
                description="Run type for the graph creation process.",
            ),
            run_with_orchestration: bool = Query(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGEnrichmentResponse:
            
            return await self._create_communities(
                id=id,
                settings=settings,
                run_type=run_type,
                run_with_orchestration=run_with_orchestration,
            )

        @self.router.post(
            "/graphs/{id}/communities",
            summary="Create communities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.communities.create(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", communities=[community1, community2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_communities(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the collection to create communities for.",
            ),
            communities: list[Community] = Body(
                ..., description="The communities to create."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            for community in communities:
                if not community.collection_id:
                    community.collection_id = id
                else:
                    if community.collection_id != id:
                        raise ValueError(
                            "Collection ID in path and body do not match"
                        )

            return await self.services["kg"].create_communities_v3(communities)

        @self.router.get(
            "/graphs/{id}/communities",
            summary="Get communities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.communities.get(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_communities(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the collection to get communities for.",
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
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            return await self.services[
                "kg"
            ].providers.database.graph_handler.communities.get(
                id=id,
                offset=offset,
                limit=limit,
            )

        @self.router.get(
            "/graphs/{id}/communities/{community_id}",
            summary="Get a community",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.communities.get(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_community(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the collection to get communities for.",
            ),
            community_id: UUID = Path(
                ...,
                description="The ID of the community to get.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            return await self.services[
                "kg"
            ].providers.database.graph_handler.communities.get(
                id=id,
                community_id=community_id,
            )

        @self.router.delete(
            "/graphs/{id}/communities/{community_id}",
            summary="Delete a community",
        )
        @self.base_endpoint
        async def delete_community(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the collection to delete the community from.",
            ),
            community_id: UUID = Path(
                ..., description="The ID of the community to delete."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            community = Community(id=community_id, collection_id=id)

            return await self.services["kg"].delete_community_v3(
                community=community,
            )

        # Graph-level operations
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
            """Deletes a graph and optionally its associated entities and relationships."""
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
            "/graphs/{id}/add/{object_type}",
            summary="Add data to a graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.add(
                                id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                data_type="entities"
                            )"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def add_data(
            id: UUID = Path(...),
            object_type: str = Path(...),
            object_ids: list[UUID] = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can add data to graphs", 403
                )

            if object_type == "documents":
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.add_documents(
                    id=id, document_ids=object_ids
                )
            elif object_type == "collections":
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.add_collections(
                    id=id, collection_ids=object_ids
                )
            elif object_type == "entities":
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.add_entities_v3(
                    id=id, entity_ids=object_ids
                )
            elif object_type == "relationships":
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.add_relationships_v3(
                    id=id, relationship_ids=object_ids
                )
            else:
                raise R2RException("Invalid data type", 400)

        # remove data
        @self.router.delete(
            "/graphs/{id}/remove/{object_type}",
            summary="Remove data from a graph",
        )
        @self.base_endpoint
        async def remove_data(
            id: UUID = Path(...),
            object_type: str = Path(...),
            object_ids: list[UUID] = Body(...),
        ):
            if object_type == "documents":
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.remove_documents(
                    id=id, document_ids=object_ids
                )
            elif object_type == "collections":
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.remove_collections(
                    id=id, collection_ids=object_ids
                )
            elif object_type == "entities":
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.remove_entities(
                    id=id, entity_ids=object_ids
                )
            elif object_type == "relationships":
                return await self.services[
                    "kg"
                ].providers.database.graph_handler.remove_relationships(
                    id=id, relationship_ids=object_ids
                )
            else:
                raise R2RException("Invalid data type", 400)

        @self.router.post(
            "/graphs/{id}/build",
            summary="Build entities, relationships, and communities in the graph",
        )
        @self.base_endpoint
        async def build(
            id: UUID = Path(...),
            settings: GraphBuildSettings = Body(GraphBuildSettings()),
        ):

            # build entities
            logger.info(f"Building entities for graph {id}")
            entities_result = await self._deduplicate_entities(
                id, settings.entity_settings, run_type=KGRunType.RUN
            )

            # build communities
            logger.info(f"Building communities for graph {id}")
            communities_result = await self._create_communities(
                id, settings.community_settings, run_type=KGRunType.RUN
            )

            return {
                "entities": entities_result,
                "communities": communities_result,
            }

        @self.router.post(
            "/graphs/{id}/build/entities",
            summary="Build entities in the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.build_entities(
                                id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def deduplicate_entities(
            id: UUID = Path(...),
            settings: Optional[dict] = Body(None),
            run_type: Optional[KGRunType] = Query(
                KGRunType.ESTIMATE,
                description="Whether to estimate cost or run deduplication",
            ),
            run_with_orchestration: bool = Query(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGEntityDeduplicationResponse:
            return await self._deduplicate_entities(
                id=id,
                settings=settings,
                run_type=run_type,
                run_with_orchestration=run_with_orchestration,
                auth_user=auth_user,
            )

        @self.router.post(
            "/graphs/{id}/communities/{community_id}",
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
                                community_id="5xyz789a-bc12-3def-4ghi-jk5lm6no7pq8",
                                community_update={
                                    "metadata": {
                                        "topic": "Technology",
                                        "description": "Tech companies and products"
                                    }
                                }
                            )"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_community(
            id: UUID = Path(...),
            community_id: UUID = Path(...),
            community: Community = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """Updates a community's metadata."""
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can update communities", 403
                )

            if not community.graph_id:
                community.graph_id = id
            else:
                if community.graph_id != id:
                    raise R2RException(
                        "Community graph ID does not match path", 400
                    )

            if not community.id:
                community.id = community_id
            else:
                if community.id != community_id:
                    raise R2RException("Community ID does not match path", 400)

            community.id = community_id
            community.graph_id = id

            return await self.services[
                "kg"
            ].providers.database.graph_handler.communities.update(community)

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
