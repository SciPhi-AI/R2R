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


class RelationshipsRouter(BaseRouterV3):

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
            "/documents/{id}/relationships",
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
                description="A list of subject or object entity names to filter the relationships by.",
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

        @self.router.get(
            "/documents/{id}/relationships/{relationship_id}",
            summary="Get a relationship for a document",
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
                ],
                "operationId": "documents_get_relationships_v3_documents__id__relationships__relationship_id__get_documents"
            },
        )
        @self.router.get(
            "/graphs/{id}/relationships/{relationship_id}",
            summary="Get a relationship for a graph",
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
                ],
                "operationId": "graphs_get_relationships_v3_graphs__id__relationships__relationship_id__get_graphs"
            },
        )
        @self.base_endpoint
        async def get_relationship(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the chunk to retrieve the relationship for.",
            ),
            relationship_id: UUID = Path(
                ...,
                description="The ID of the relationship to retrieve.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRelationshipResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            relationship = await self.services["kg"].list_relationships_v3(
                level=self._get_path_level(request),
                id=id,
                relationship_id=relationship_id,
            )

            return relationship

        @self.router.post(
            "/documents/{id}/relationships",
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
                ],
                "operationId": "documents_create_relationships_v3_documents__id__relationships_post_documents"
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
                ],
                "operationId": "graphs_create_relationships_v3_graphs__id__relationships_post_graphs"
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
                ],
                "operationId": "documents_update_relationships_v3_documents__id__relationships__relationship_id__post_documents"
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
                ],
                "operationId": "graphs_update_relationships_v3_graphs__id__relationships__relationship_id__post_graphs"
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
            "/documents/{id}/relationships/{relationship_id}",
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
                ],
                "operationId": "documents_delete_relationships_v3_documents__id__relationships__relationship_id__delete_documents"
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
                ],
                "operationId": "documents_delete_relationships_v3_documents__id__relationships__relationship_id__delete_documents"
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
