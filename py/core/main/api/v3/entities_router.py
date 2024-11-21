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
            "/entities",
            summary="List entities",
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
            },
        )
        @self.base_endpoint
        async def list_entities(
            request: Request,
            graph_id: Optional[UUID] = Query(
                None,
                description="The ID of the graph to retrieve entities for.",
            ),
            document_id: Optional[UUID] = Query(
                None,
                description="The ID of the document to retrieve entities for.",
            ),
            entity_names: Optional[list[str]] = Query(
                None,
                description="A list of entity names to filter the entities by.",
            ),
            include_embeddings: bool = Query(
                False,
                description="Whether to include vector embeddings in the response.",
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
            Returns a paginated list of entities from a knowledge graph or document.

            You must provide either a graph_id or a document_id.

            The entities can be filtered by:
            - Graph ID: Get entities from a specific graph
            - Document ID: Get entities from a specific document 
            - Entity names: Filter by specific entity names
            - Include embeddings: Whether to include vector embeddings in the response

            The response includes:
            - List of entity objects with their attributes
            - Total count of matching entities
            """

            if not graph_id and not document_id:
                raise ValueError("Either graph_id or document_id must be provided.")

            entities, count = await self.services["kg"].list_entities(
                id=id,
                graph_id=graph_id,
                document_id=document_id,
                offset=offset,
                limit=limit,
                entity_names=entity_names,
                include_embeddings=include_embeddings,
                user_id=user_id,
            )

            return entities, {  # type: ignore
                "total_entries": count,
            }

        @self.router.get(
            "/entities/{id}",
            summary="Retrieve an entity",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.entities.get(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_entity(
            id: UUID = Path(
                ...,
                description="The ID of the entity to retrieve.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedEntityResponse:
            """
            Retrieves detailed information about a specific entity by its unique identifier.

            The attributes parameter allows selective retrieval of specific entity properties to optimize response size and processing.
            """

            entity = await self.services["kg"].get_entity(
                id=id,
            )

            graph_ids = entity.graph_ids
            document_ids = entity.document_ids

            # if the user does not have access to the graph or the document, return a 403



            return entity

        @self.router.post(
            "/entities",
            summary="Create entities",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.entities.create([entity1, entity2])
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def create_entities_v3(
            request: Request,
            entities: list[Entity] = Body(
                ..., description="The entities to create."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Creates new entities.

            This endpoint allows you to:
            1. Create multiple entities in a single request by providing a list of entity objects
            2. Define entity attributes, types, and metadata
            3. Automatically generate unique IDs for each entity
            4. Link entities to existing graphs or documents

            Entity IDs are automatically generated by the server and returned in the response.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            for entity in entities:
                if entity.id or entity.sid:
                    raise R2RException("Cannot provide id or sid, they are generated by the server.", 400)

            res = await self.services["kg"].create_entities(
                entities=entities,
            )

            return res

        @self.router.post(
            "/entities/{id}",
            summary="Update an entity",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.entities.update(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", entity=entity)
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def update_entity(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the entity to update.",
            ),
            entity: Entity = Body(..., description="The updated entity."),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Updates an existing entity in the database.

            This endpoint allows you to modify:
            - Entity attributes and properties
            - Entity type and classification
            - Entity metadata and tags
            - Graph and document associations

            Any fields not included in the update request will retain their existing values.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            entity.id = id

            return await self.services["kg"].update_entity_v3(
                entity=entity,
            )

        @self.router.delete(
            "/entities/{id}",
            summary="Delete an entity",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.entities.delete(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ],
            },
        )
        @self.base_endpoint
        async def delete_entity(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to delete the entity for.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
                Deletes an entity and all its associated data.

                This endpoint permanently removes:
                - The entity itself and all its attributes

                However, this will not remove any relationships or communities that the entity is part of.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            return await self.services["kg"].delete_entity_v3(
                id=id,
                level=self._get_path_level(request),
            )
