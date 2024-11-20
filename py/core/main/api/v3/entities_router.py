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


class EntitiesRouter(BaseRouterV3):
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

    def _setup_routes(self):

        @self.router.get(
            "/documents/{id}/entities",
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
                ],
                "operationId": "documents_list_entities_v3_documents__id__entities_get_documents",
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
                ],
                "operationId": "graphs_list_entities_v3_graphs__id__entities_get_graphs",
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
            This endpoint returns a paginated list of entities associated for the specified object.

            Results can be filtered by the optional query parameters like entity_names.

            By default, all attributes are returned, but they can be filtered by the optional query parameter attributes.
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
                attributes=attributes,
            )

            return entities, {  # type: ignore
                "total_entries": count,
            }

        @self.router.get(
            "/documents/{id}/entities/{entity_id}",
            summary="Get an entity for a document",
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
            "/graphs/{id}/entities/{entity_id}",
            summary="Get an entity for a graph",
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
        async def get_entity(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the object to retrieve the entity for.",
            ),
            entity_id: UUID = Path(
                ..., description="The ID of the entity to retrieve."
            ),
        ) -> WrappedEntityResponse:

            entity = await self.services["kg"].get_entity(
                level=self._get_path_level(request),
                id=id,
                entity_id=entity_id,
            )

            return entity

        @self.router.post(
            "/documents/{id}/entities",
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

                            result = client.documents.entities.create(document_id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entities=[entity1, entity2])
                            """
                        ),
                    },
                ],
                "operationId": "documents_create_entities_v3_documents__id__entities_post_documents",
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
                ],
                "operationId": "graphs_create_entities_v3_graphs__id__entities_post_graphs",
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
            """
            This endpoint creates entities for the specified object.

            The endpoint expects a list of entities to be provided in the request body.
            """
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
                ],
                "operationId": "documents_update_entities_v3_documents__id__entities__entity_id__post_documents",
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
                ],
                "operationId": "graphs_update_entities_v3_graphs__id__entities__entity_id__post_graphs",
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
            """
            Updates an existing entity in the database.

            The entity can be updated by providing the entity ID and the updated entity object in the request body.
            """
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
            "/documents/{id}/entities/{entity_id}",
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
                ],
                "operationId": "documents_delete_entities_v3_documents__id__entities__entity_id__delete_documents",
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
                ],
                "operationId": "graphs_delete_entities_v3_graphs__id__entities__entity_id__delete_graphs",
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
