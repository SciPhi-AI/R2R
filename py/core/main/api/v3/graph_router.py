import logging
import textwrap
from typing import Optional, Union
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel, Field

from core.base import R2RException, RunType
from core.base.abstractions import EntityLevel, KGRunType
from core.base.abstractions import Community, Entity, Relationship

from core.base.api.models import (
    WrappedKGCreationResponseV3 as WrappedKGCreationResponse,
    WrappedKGEnrichmentResponseV3 as WrappedKGEnrichmentResponse,
    WrappedKGEntityDeduplicationResponseV3 as WrappedKGEntityDeduplicationResponse,
    WrappedKGTunePromptResponseV3 as WrappedKGTunePromptResponse,
    WrappedKGRelationshipsResponseV3 as WrappedKGRelationshipsResponse,
    WrappedKGCommunitiesResponseV3 as WrappedKGCommunitiesResponse,
    KGCreationResponseV3 as KGCreationResponse,
    KGEnrichmentResponseV3 as KGEnrichmentResponse,
    KGEntityDeduplicationResponseV3 as KGEntityDeduplicationResponse,
    KGTunePromptResponseV3 as KGTunePromptResponse,
    WrappedKGEntitiesResponseV3 as WrappedKGEntitiesResponse,
    WrappedKGRelationshipsResponseV3 as WrappedKGRelationshipsResponse,
    WrappedKGCommunitiesResponseV3 as WrappedKGCommunitiesResponse,
    WrappedKGDeletionResponseV3 as WrappedKGDeletionResponse,
)


from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from core.utils import (
    generate_default_user_collection_id,
    update_settings_from_dict,
)

from core.base.api.models import PaginatedResultsWrapper, ResultsWrapper

from core.base.abstractions import Entity, KGCreationSettings, Relationship

from .base_router import BaseRouterV3

from fastapi import Request

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

    def _get_path_level(self, request: Request) -> EntityLevel:
        path = request.url.path
        if "/chunks/" in path:
            return EntityLevel.CHUNK
        elif "/documents/" in path:
            return EntityLevel.DOCUMENT
        else:
            return EntityLevel.COLLECTION

    def _setup_routes(self):

        # create graph new endpoint
        @self.router.post(
            "/documents/{id}/graphs/{run_type}",
        )
        @self.base_endpoint
        async def create_graph(
            id: UUID = Path(..., description="The ID of the document to create a graph for."),
            run_type: KGRunType = Path(
                description="Run type for the graph creation process.",
            ),
            settings: Optional[KGCreationSettings] = Body(
                default=None,
                description="Settings for the graph creation process.",
            ),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGCreationResponse:
            """
                Creates a new knowledge graph by extracting entities and relationships from a document.
                    The graph creation process involves:
                    1. Parsing documents into semantic chunks
                    2. Extracting entities and relationships using LLMs or NER
            """

            settings = settings.dict() if settings else None
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
                    server_kg_creation_settings, settings
                )

            # If the run type is estimate, return an estimate of the creation cost
            if run_type is KGRunType.ESTIMATE:
                raise NotImplementedError("Estimate is not implemented yet.")
                # return await self.services["kg"].get_creation_estimate(
                #     document_id = id, settings=server_kg_creation_settings
                # )
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
                    simple_kg = simple_kg_factory(self.service)
                    await simple_kg["create-graph"](workflow_input)
                    return {
                        "message": "Graph created successfully.",
                        "task_id": None,
                    }

        ##### ENTITIES ######
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

                            result = client.chunks.graphs.list_entities(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=100)
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

                            result = client.documents.graphs.list_entities(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=100)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.get(
            "/collections/{id}/graphs/entities",
            summary="List entities for a collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.graphs.list_entities(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", offset=0, limit=100)
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
                description="The ID of the chunk to retrieve entities for.",
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
                description="The offset of the first entity to retrieve.",
            ),
            limit: int = Query(
                100,
                ge=0,
                le=20_000,
                description="The maximum number of entities to retrieve, up to 20,000.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[list[Entity]]:
            """
            Retrieves a list of entities associated with a specific chunk.

            Note that when entities are extracted, neighboring chunks are also processed together to extract entities.

            So, the entity returned here may not be in the same chunk as the one specified, but rather in a neighboring chunk (upto 2 chunks by default).
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            entities, count = await self.services["kg"].list_entities_v3(
                level=self._get_path_level(request),
                id=id,
                offset=offset,
                limit=limit,
                entity_names=entity_names,
                entity_categories=entity_categories,
                attributes=attributes,
            )

            return entities, {
                "total_entries": count,
            }

        @self.router.post(
            "/chunks/{id}/graphs/entities",
            summary="Create entities for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.graphs.create_entities_v3(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entities=[entity1, entity2])
                            """
                        ),
                    },
                ]
            },
        )
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

                            result = client.documents.graphs.create_entities_v3(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entities=[entity1, entity2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/collections/{id}/graphs/entities",
            summary="Create entities for a collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.graphs.create_entities_v3(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entities=[entity1, entity2])
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
                level = EntityLevel.CHUNK
            elif "/documents/" in path:
                level = EntityLevel.DOCUMENT
            else:
                level = EntityLevel.COLLECTION

            # set entity level if not set
            for entity in entities:
                if entity.level:
                    if entity.level != level:
                        raise R2RException(
                            "Entity level must match the path level.", 400
                        )
                else:
                    entity.level = level

            # depending on the level, perform validation
            if level == EntityLevel.CHUNK:
                for entity in entities:
                    if entity.chunk_ids and id not in entity.chunk_ids:
                        raise R2RException(
                            "Entity extraction IDs must include the chunk ID or should be empty.", 400
                        )

            elif level == EntityLevel.DOCUMENT:
                for entity in entities:
                    if entity.document_id:
                        if entity.document_id != id:
                            raise R2RException(
                                "Entity document IDs must match the document ID or should be empty.", 400
                            )
                    else:
                        entity.document_id = id

            elif level == EntityLevel.COLLECTION:
                for entity in entities:
                    if entity.collection_id:
                        if entity.collection_id != id:
                            raise R2RException(
                                "Entity collection IDs must match the collection ID or should be empty.", 400
                            )
                    else:
                        entity.collection_id = id

            return await self.services["kg"].create_entities_v3(
                entities=entities,
            )

        @self.router.post(
            "/chunks/{id}/graphs/entities/{entity_id}",
            summary="Update an entity for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.graphs.update_entity(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000", entity=entity)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/documents/{id}/graphs/entities/{entity_id}",
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

                            result = client.documents.graphs.update_entity(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000", entity=entity)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/collections/{id}/graphs/entities/{entity_id}",
            summary="Update an entity for a collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.graphs.update_entity(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000", entity=entity)
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

            if entity.level == EntityLevel.CHUNK:
                # don't override the chunk_ids
                entity.chunk_ids = None

            elif entity.level == EntityLevel.DOCUMENT:
                entity.document_id = id

            elif entity.level == EntityLevel.COLLECTION:
                entity.collection_id = id

            if not entity.id:
                entity.id = entity_id
            else:
                if entity.id != entity_id:
                    raise R2RException(
                        "Entity ID must match the entity ID or should be empty.", 400
                    )

            return await self.services["kg"].update_entity_v3(
                entity=entity,
            )

        @self.router.delete(
            "/chunks/{id}/graphs/entities/{entity_id}",
            summary="Delete an entity for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.graphs.delete_entity(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
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

                            result = client.documents.graphs.delete_entity(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.delete(
            "/collections/{id}/graphs/entities/{entity_id}",
            summary="Delete an entity for a collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.graphs.delete_entity(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity_id="123e4567-e89b-12d3-a456-426614174000")
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
                description="The ID of the chunk to delete the entity for.",
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

            entity = Entity(id=entity_id, level=self._get_path_level(request))

            return await self.services["kg"].delete_entity_v3(
                entity=entity,
            )

        ##### RELATIONSHIPS #####
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

                            result = client.chunks.graphs.list_relationships(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
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

                            result = client.documents.graphs.list_relationships(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.get(
            "/chunks/{id}/relationships",
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

                            result = client.collections.graphs.list_relationships(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
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
                description="The offset of the first relationship to retrieve.",
            ),
            limit: int = Query(
                100,
                ge=0,
                le=20_000,
                description="The maximum number of relationships to retrieve, up to 20,000.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[list[Relationship]]:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            relationships, count = await self.services["kg"].list_relationships_v3(
                level=self._get_path_level(request),
                id=id,
                entity_names=entity_names,
                relationship_types=relationship_types,
                attributes=attributes,
                offset=offset,
                limit=limit,
            )

            return relationships, {
                "total_entries": count,
            }

        @self.router.post(
            "/chunks/{id}/graphs/relationships",
            summary="Create relationships for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.graphs.create_relationships(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationships=[relationship1, relationship2])
                            """
                        ),
                    },
                ]
            },
        )
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

                            result = client.documents.graphs.create_relationships(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationships=[relationship1, relationship2])
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/collections/{id}/graphs/relationships",
            summary="Create relationships for a collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.graphs.create_relationships(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationships=[relationship1, relationship2])
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

            return {
                "message": "Relationships created successfully.",
                "count": await self.services["kg"].create_relationships_v3(
                    id=id,
                    relationships=relationships,
                ),
            }

        @self.router.post(
            "/chunks/{id}/graphs/relationships/{relationship_id}",
            summary="Update a relationship for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.graphs.update_relationship(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000", relationship=relationship)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/documents/{id}/graphs/relationships/{relationship_id}",
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

                            result = client.documents.update_relationship(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000", relationship=relationship)
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.post(
            "/collections/{id}/graphs/relationships/{relationship_id}",
            summary="Update a relationship for a collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.graphs.update_relationship(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000", relationship=relationship)
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
                    raise ValueError("Relationship ID in path and body do not match")

            return await self.services["kg"].update_relationship_v3(
                relationship=relationship,
            )

        @self.router.delete(
            "/chunks/{id}/graphs/relationships/{relationship_id}",
            summary="Delete a relationship for a chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.graphs.delete_relationship(chunk_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
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

                            result = client.documents.graphs.delete_relationship(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000")
                            """
                        ),
                    },
                ]
            },
        )
        @self.router.delete(
            "/collections/{id}/graphs/relationships/{relationship_id}",
            summary="Delete a relationship for a collection",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.collections.graphs.delete_relationship(collection_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship_id="123e4567-e89b-12d3-a456-426614174000")
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
            if level == EntityLevel.CHUNK:
                chunk_ids = [id]
                relationship = Relationship(id = relationship_id, chunk_ids = chunk_ids)
            elif level == EntityLevel.DOCUMENT:
                relationship = Relationship(id = relationship_id, document_id = id)
            else:
                relationship = Relationship(id = relationship_id, collection_id = id)

            return await self.services["kg"].delete_relationship_v3(
                relationship=relationship,
            )


        ################### COMMUNITIES ###################

        @self.router.post(
            "/collections/{id}/graphs/",
        )
        @self.base_endpoint
        async def create_communities(
            request: Request,
            id: UUID = Path(..., description="The ID of the collection to create communities for."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            # run enrich graph workflow

        @self.router.post(
            "/collections/{id}/graphs/communities",
            summary="Create communities",
        )
        @self.base_endpoint
        async def create_communities(
            request: Request,
            id: UUID = Path(..., description="The ID of the collection to create communities for."),
            communities: list[Community] = Body(..., description="The communities to create."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            for community in communities:
                if not community.collection_id:
                    community.collection_id = id
                else:
                    if community.collection_id != id:
                        raise ValueError("Collection ID in path and body do not match")

            return await self.services["kg"].create_communities_v3(communities)


        @self.router.get(
            "/collections/{id}/graphs/communities",
            summary="Get communities",
        )
        @self.base_endpoint
        async def get_communities(
            request: Request,
            id: UUID = Path(..., description="The ID of the collection to get communities for."),
            offset: int = Query(0, description="Number of communities to skip"),
            limit: int = Query(100, description="Maximum number of communities to return"),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            return await self.services["kg"].get_communities_v3(
                collection_id=id,
                offset=offset,
                limit=limit,
            )

        @self.router.delete(
            "/collections/{id}/graphs/communities/{community_id}",
            summary="Delete a community",
        )
        @self.base_endpoint
        async def delete_community(
            request: Request,
            id: UUID = Path(..., description="The ID of the collection to delete the community from."),
            community_id: UUID = Path(..., description="The ID of the community to delete."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can access this endpoint.", 403)

            community = Community(id=community_id, collection_id=id)

            return await self.services["kg"].delete_community_v3(
                community=community,
            )


        ################### GRAPHS ###################

        @self.base_endpoint
        async def create_entities(
            request: Request,
        ):
            pass

        # Graph-level operations
        @self.router.post(
            "/graphs/",
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
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                settings={
                                    "entity_types": ["PERSON", "ORG", "GPE"]
                                }
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "settings": {
                                        "entity_types": ["PERSON", "ORG", "GPE"]
                                    }
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_empty_graph(
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            pass

        @self.router.get(
            "/graphs/{collection_id}",
            summary="Get graph status",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.get_status(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
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
        async def get_graph_status(
            collection_id: UUID = Path(...),  # TODO: change to id?
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[dict]:
            """
            Gets the status and metadata of a graph for a collection.

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

            # status = await self.services["kg"].get_graph_status(collection_id)
            # return status  # type: ignore

        # @self.router.post(
        #     "/graphs/{collection_id}/enrich",
        #     summary="Enrich an existing graph",
        #     openapi_extra={
        #         "x-codeSamples": [
        #             {
        #                 "lang": "Python",
        #                 "source": textwrap.dedent(
        #                     """
        #                     from r2r import R2RClient

        #                     client = R2RClient("http://localhost:7272")
        #                     # when using auth, do client.login(...)

        #                     result = client.graphs.enrich(
        #                         collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
        #                         settings={
        #                             "community_detection": {
        #                                 "algorithm": "louvain",
        #                                 "resolution": 1.0
        #                             },
        #                             "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
        #                         }
        #                     )"""
        #                 ),
        #             },
        #             {
        #                 "lang": "cURL",
        #                 "source": textwrap.dedent(
        #                     """
        #                     curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/enrich" \\
        #                         -H "Content-Type: application/json" \\
        #                         -H "Authorization: Bearer YOUR_API_KEY" \\
        #                         -d '{
        #                             "settings": {
        #                                 "community_detection": {
        #                                     "algorithm": "louvain",
        #                                     "resolution": 1.0
        #                                 },
        #                                 "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
        #                             }
        #                         }'"""
        #                 ),
        #             },
        #         ]
        #     },
        # )
        # @self.base_endpoint
        # async def enrich_graph(
        #     collection_id: UUID = Path(...),
        #     settings: Optional[dict] = Body(None),
        #     run_with_orchestration: bool = Query(True),
        #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # ) -> ResultsWrapper[WrappedKGEnrichmentResponse]:
        #     """Enriches an existing graph with additional information and creates communities."""
        #     if not auth_user.is_superuser:
        #         raise R2RException("Only superusers can enrich graphs", 403)

        #     server_settings = self.providers.database.config.kg_enrichment_settings
        #     if settings:
        #         server_settings = update_settings_from_dict(server_settings, settings)

        #     workflow_input = {
        #         "collection_id": str(collection_id),
        #         "kg_enrichment_settings": server_settings.model_dump_json(),
        #         "user": auth_user.model_dump_json(),
        #     }

        #     if run_with_orchestration:
        #         return await self.orchestration_provider.run_workflow(
        #             "enrich-graph", {"request": workflow_input}, {}
        #         )
        #     else:
        #         from core.main.orchestration import simple_kg_factory
        #         simple_kg = simple_kg_factory(self.services["kg"])
        #         await simple_kg["enrich-graph"](workflow_input)
        #         return {"message": "Graph enriched successfully.", "task_id": None}

        @self.router.delete(
            "/graphs/{collection_id}",
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
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                cascade=True
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7?cascade=true" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_graph(
            collection_id: UUID = Path(...),
            cascade: bool = Query(False),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[dict]:
            """Deletes a graph and optionally its associated entities and relationships."""
            if not auth_user.is_superuser:
                raise R2RException("Only superusers can delete graphs", 403)

            await self.services["kg"].delete_graph(collection_id, cascade)
            return {"message": "Graph deleted successfully"}  # type: ignore

        @self.base_endpoint
        async def deduplicate_entities(
            collection_id: UUID = Path(...),
            settings: Optional[dict] = Body(None),
            run_type: Optional[KGRunType] = Query(
                KGRunType.ESTIMATE,
                description="Whether to estimate cost or run deduplication",
            ),
            run_with_orchestration: bool = Query(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[WrappedKGEntityDeduplicationResponse]:
            """Deduplicates entities in the knowledge graph using LLM-based analysis.

            The deduplication process:
            1. Groups potentially duplicate entities by name/type
            2. Uses LLM analysis to determine if entities refer to same thing
            3. Merges duplicate entities while preserving relationships
            4. Updates all references to use canonical entity IDs

            Args:
                collection_id (UUID): Collection containing the graph
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
                raise R2RException(
                    "Only superusers can deduplicate entities", 403
                )

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
                "collection_id": str(collection_id),
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

        @self.base_endpoint
        async def create_communities(
            collection_id: UUID = Path(...),
            settings: Optional[dict] = Body(None),
            run_type: Optional[KGRunType] = Body(
                default=None,
                description="Run type for the graph creation process.",
            ),
            run_with_orchestration: bool = Query(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
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
                "collection_id": str(collection_id),
                "kg_enrichment_settings": server_kg_enrichment_settings.model_dump_json(),
                "user": auth_user.model_dump_json(),
            }

            if not run_type:
                run_type = KGRunType.ESTIMATE

            # If the run type is estimate, return an estimate of the enrichment cost
            if run_type is KGRunType.ESTIMATE:
                return await self.services["kg"].get_enrichment_estimate(
                    collection_id, server_kg_enrichment_settings
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
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities/5xyz789a-bc12-3def-4ghi-jk5lm6no7pq8" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                    "metadata": {
                                        "topic": "Technology",
                                        "description": "Tech companies and products"
                                    }
                                }'"""
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_community(
            collection_id: UUID = Path(...),
            community_id: UUID = Path(...),
            community_update: dict = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[Community]:
            """Updates a community's metadata."""
            raise NotImplementedError("Not implemented")
            # if not auth_user.is_superuser:
            #     raise R2RException(
            #         "Only superusers can update communities", 403
            #     )

            # updated_community = await self.services["kg"].update_community(
            #     collection_id, community_id, community_update
            # )
            # return updated_community  # type: ignore

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

                            result = client.graphs.list_communities(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                level=1,
                                offset=0,
                                limit=100
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities?\\
                                level=1&offset=0&limit=100" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_communities(
            collection_id: UUID = Path(...),
            level: Optional[int] = Query(None),
            offset: int = Query(0, ge=0),
            limit: int = Query(100, ge=1, le=1000),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> (
            WrappedKGCommunitiesResponse
        ):  # PaginatedResultsWrapper[list[Community]]:
            """Lists communities in the graph with optional filtering and pagination.

            Each community represents a group of related entities with:
            - Community number and hierarchical level
            - Member entities and relationships
            - Generated name and summary
            - Key findings and insights
            - Impact rating and explanation
            """
            communities = await self.services["kg"].list_communities(
                collection_id, levels, community_numbers, offset, limit
            )
            return communities  # type: ignore

        @self.router.get(
            "/graphs/{collection_id}/communities/{community_id}",
            summary="Get community details",
        )
        @self.base_endpoint
        async def get_community(
            collection_id: UUID = Path(...),
            community_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[Community]:
            """Retrieves details of a specific community."""
            raise NotImplementedError("Not implemented")
            # community = await self.services["kg"].get_community(
            #     collection_id, community_id
            # )
            # if not community:
            #     raise R2RException("Community not found", 404)
            # return community  # type: ignore

        @self.router.delete(
            "/graphs/{collection_id}/communities",
            summary="Delete all communities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            # Delete all communities
                            result = client.graphs.delete_communities(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7"
                            )

                            # Delete specific level
                            result = client.graphs.delete_communities(
                                collection_id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                level=1
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            # Delete all communities
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities" \\
                                -H "Authorization: Bearer YOUR_API_KEY"

                            # Delete specific level
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities?level=1" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_communities(
            collection_id: UUID = Path(...),
            level: Optional[int] = Query(
                None,
                description="Specific community level to delete. If not provided, all levels will be deleted.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[dict]:
            """
            Deletes communities from the graph. Can delete all communities or a specific level.
            This is useful when you want to recreate communities with different parameters.
            """
            raise NotImplementedError("Not implemented")
            # if not auth_user.is_superuser:
            #     raise R2RException(
            #         "Only superusers can delete communities", 403
            #     )

            # await self.services["kg"].delete_communities(collection_id, level)

            # if level is not None:
            #     return {  # type: ignore
            #         "message": f"Communities at level {level} deleted successfully"
            #     }
            # return {"message": "All communities deleted successfully"}  # type: ignore

        @self.router.delete(
            "/graphs/{collection_id}/communities/{community_id}",
            summary="Delete a specific community",
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
                                community_id="5xyz789a-bc12-3def-4ghi-jk5lm6no7pq8"
                            )"""
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/v3/graphs/d09dedb1-b2ab-48a5-b950-6e1f464d83e7/communities/5xyz789a-bc12-3def-4ghi-jk5lm6no7pq8" \\
                                -H "Authorization: Bearer YOUR_API_KEY" """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_community(
            collection_id: UUID = Path(...),
            community_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedKGDeletionResponse:
            """
            Deletes a specific community by ID.
            This operation will not affect other communities or the underlying entities.
            """
            raise NotImplementedError("Not implemented")
            # if not auth_user.is_superuser:
            #     raise R2RException(
            #         "Only superusers can delete communities", 403
            #     )

            # # First check if community exists
            # community = await self.services["kg"].get_community(
            #     collection_id, community_id
            # )
            # if not community:
            #     raise R2RException("Community not found", 404)

            await self.services["kg"].delete_community(
                collection_id, community_id
            )
            return True  # type: ignore

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
