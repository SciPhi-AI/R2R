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
            "/relationships",
            summary="List relationships",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.relationships.list(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
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
            graph_id: Optional[UUID] = Query(
                None,
                description="The ID of the graph to retrieve relationships for.",
            ),
            document_id: Optional[UUID] = Query(
                None,
                description="The ID of the document to retrieve relationships for.",
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
                graph_id=graph_id,
                document_id=document_id,
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
            "/relationships/{id}",
            summary="Get a relationship",
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
                "operationId": "graphs_get_relationships_v3_graphs__id__relationships__relationship_id__get_graphs",
            },
        )
        @self.base_endpoint
        async def get_relationship(
            request: Request,
            id: UUID = Path(
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
            )

            return relationship

        @self.router.post(
            "/relationships",
            summary="Create relationships",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.relationships.create(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationships=[relationship1, relationship2])
                            """
                        ),
                    },
                ],
                "operationId": "create_relationships_v3_relationships_post_relationships",
            },
        )
        @self.base_endpoint
        async def create_relationships(
            request: Request,
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
                relationships=relationships,
            )

            return {  # type: ignore
                "message": "Relationships created successfully.",
                "count": relationships,
            }

        @self.router.post(
            "/relationships/{id}",
            summary="Update a relationship",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.relationships.update(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1", relationship=relationship)
                            """
                        ),
                    },
                ],
                "operationId": "update_relationships_v3_relationships__id__post_relationships",
            },
        )
        @self.base_endpoint
        async def update_relationship(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the relationship to update.",
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

            return await self.services["kg"].update_relationship_v3(
                relationship=relationship,
            )

        @self.router.delete(
            "/relationships/{id}",
            summary="Delete a relationship",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.relationships.delete(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ],
                "operationId": "delete_relationships_v3_relationships__id__delete_relationships",
            },
        )
        @self.base_endpoint
        async def delete_relationship(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the relationship to delete.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            return await self.services["kg"].delete_relationship_v3(
                id=id,
            )
