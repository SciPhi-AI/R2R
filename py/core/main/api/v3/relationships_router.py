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
    GenericBooleanResponse,
    WrappedBooleanResponse,
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

                            result = client.relationships.list(ids=["9fbe403b-c11c-5aae-8ade-ef22980c3ad1"])
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
                                const response = await client.relationships.list({
                                    ids: ["9fbe403b-c11c-5aae-8ade-ef22980c3ad1"],
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
        async def list_relationships(
            ids: Optional[list[UUID]] = Query(
                None,
                description="A list of relationship IDs to retrieve. If not provided, all relationships will be returned.",
            ),
            offset: int = Query(
                0,
                ge=0,
                description="Specifies the number of objects to skip. Defaults to 0.",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=100,
                description="Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRelationshipsResponse:
            """
            Lists all relationships in the graph with pagination support.

            Relationships can be filtered by:
            - Graph ID
            - Document ID
            - Entity names
            - Relationship types

            By default, all attributes are returned, but this can be limited using the `attributes` parameter.
            """

            requesting_user_id = (
                None if auth_user.is_superuser else [auth_user.id]
            )

            list_relationships_response = await self.services[
                "kg"
            ].list_relationships_v3(
                filter_user_ids=requesting_user_id,
                filter_relationship_ids=ids,
                offset=offset,
                limit=limit,
            )

            return list_relationships_response["results"], {
                "total_entries": list_relationships_response["total_entries"]
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
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");
                            const client = new r2rClient("http://localhost:7272");
                            function main() {
                                const response = client.relationships.get({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
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
            id: UUID = Path(
                ...,
                description="The ID of the relationship to retrieve.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRelationshipResponse:
            """
            Retrieves a relationship by its ID.

            By default, all attributes are returned, but this can be limited using the `attributes` parameter.
            """

            list_relationships_response = await self.services[
                "kg"
            ].list_relationships_v3(
                filter_relationship_ids=[id],
                offset=0,
                limit=1,
            )

            return list_relationships_response["results"][0]

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

                            result = client.relationships.create(
                                subject="subject",
                                predicate="predicate",
                                object="object",
                                description="description",
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
                                const response = client.relationships.create({
                                    subject: "subject",
                                    predicate: "predicate",
                                    object: "object",
                                    description: "description",
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
        async def create_relationships(
            subject: str = Body(
                ..., description="The subject of the relationship"
            ),
            predicate: str = Body(
                ..., description="The predicate of the relationship"
            ),
            object: str = Body(
                ..., description="The object of the relationship"
            ),
            description: str = Body(
                ..., description="The description of the relationship"
            ),
            weight: Optional[float] = Body(
                1.0,
                description="The weight of the relationship",
            ),
            attributes: Optional[dict] = Body(
                {},
                description="The attributes of the relationship",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRelationshipResponse:
            """
            Creates a new relationship in the database.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            relationships = await self.services["kg"].create_relationships_v3(
                subject=subject,
                predicate=predicate,
                object=object,
                description=description,
                weight=weight,
                attributes=attributes,
                user_id=auth_user.id,
            )

            return relationships

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

                            result = client.relationships.update(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                subject="subject",
                                predicate="predicate",
                                object="object",
                                description="description",
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
                                const response = client.relationships.update({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    subject: "subject",
                                    predicate: "predicate",
                                    object: "object",
                                    description: "description",
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
        async def update_relationship(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the relationship to update.",
            ),
            subject: Optional[str] = Body(
                None, description="The subject of the relationship"
            ),
            predicate: Optional[str] = Body(
                None, description="The predicate of the relationship"
            ),
            object: Optional[str] = Body(
                None, description="The object of the relationship"
            ),
            description: Optional[str] = Body(
                None, description="The description of the relationship"
            ),
            weight: Optional[float] = Body(
                None, description="The weight of the relationship"
            ),
            attributes: Optional[dict] = Body(
                None, description="The attributes of the relationship"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedRelationshipResponse:
            """
            Updates an existing relationship in the database.

            This endpoint allows you to modify:
            - Relationship type and classification
            - Relationship attributes and properties
            - Source and target entity connections
            - Relationship metadata and tags

            Any fields not included in the update request will retain their existing values.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            return await self.services["kg"].update_relationship_v3(
                relationship_id=id,
                subject=subject,
                predicate=predicate,
                object=object,
                description=description,
                weight=weight,
                attributes=attributes,
                user_id=auth_user.id,
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
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");
                            const client = new r2rClient("http://localhost:7272");
                            function main() {
                                const response = client.relationships.delete({
                                    id: "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                });
                            }
                            main();
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
        ) -> WrappedBooleanResponse:
            """
            Deletes a relationship by its ID.

            Note that this will not delete the source or target entities of the relationship.

            This will also not delete the relationship from any communities that it is part of.

            This operation cannot be undone.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            await self.services["kg"].delete_relationship_v3(
                id=id,
            )

            return GenericBooleanResponse(success=True)
