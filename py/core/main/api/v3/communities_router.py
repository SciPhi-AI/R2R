import logging
import textwrap
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query

from core.base import R2RException, RunType
from core.base.abstractions import DataLevel, KGRunType
from core.base.abstractions import Community, Entity, Relationship, Graph

from core.base.api.models import (
    GenericBooleanResponse,
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


class CommunitiesRouter(BaseRouterV3):
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

    async def _create_communities(
        self,
        graph_id: UUID,
        settings,
        run_type: Optional[KGRunType] = KGRunType.ESTIMATE,
        run_with_orchestration: bool = True,
        auth_user=None,
    ) -> WrappedKGEnrichmentResponse:
        """Creates communities in the graph by analyzing entity relationships and similarities.

        Communities are created through the following process:
        1. Analyzes entity relationships and attributes to build a similarity graph
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
        if not auth_user.is_superuser:
            raise R2RException("Only superusers can create communities", 403)

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
            return {  # type: ignore
                "message": "Ran community build estimate.",
                "estimate": await self.services["kg"].get_enrichment_estimate(
                    graph_id=graph_id,
                    kg_enrichment_settings=server_kg_enrichment_settings,
                ),
            }

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

        @self.router.post(
            "/graphs/{id}/communities/build",
            summary="Build communities for the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.communities.build(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1")
                            """
                        ),
                    },
                ],
                "operationId": "graphs_build_communities_v3_graphs__id__communities_build_graphs",
            },
        )
        @self.base_endpoint
        async def create_communities(
            id: UUID = Path(...),
            settings: Optional[dict] = Body(None),
            run_type: Optional[KGRunType] = Query(
                description="Run type for the graph creation process.",
            ),
            run_with_orchestration: bool = Query(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCommunityResponse:
            """Creates communities in the graph by analyzing entity relationships and similarities.

            Communities are created through the following process:
            1. Analyzes entity relationships and attributes to build a similarity graph
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
                graph_id=id,
                settings=settings,
                run_type=run_type,
                run_with_orchestration=run_with_orchestration,
                auth_user=auth_user,
            )

        @self.router.post(
            "/graphs/{id}/communities",
            summary="Create a new community in the graph",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.graphs.communities.create(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                name="My Community",
                                summary="A summary of the community",
                                findings=["Finding 1", "Finding 2"],
                                level=0,
                                rating=5,
                                rating_explanation="Explanation for the rating",
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
                                const response = client.graphs.communities.create(
                                    id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    name="My Community",
                                    summary="A summary of the community",
                                    findings=["Finding 1", "Finding 2"],
                                    level=0,
                                    rating=5,
                                    rating_explanation="Explanation for the rating",
                                );
                            }
                            main();
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_communities(
            id: UUID = Path(
                ...,
                description="The ID of the graph to create the community in.",
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
        ) -> WrappedCommunityResponse:
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

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to create a community in this graph.",
                    403,
                )

            return await self.services["kg"].create_community_v3(
                graph_id=id,
                name=name,
                summary=summary,
                findings=findings,
                rating=rating,
                rating_explanation=rating_explanation,
                level=level,
                attributes=attributes,
                user_id=auth_user.id,
            )

        @self.router.get(
            "/graphs/{id}/communities",
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

                            result = client.graphs.communities.list(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
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
                                const response = client.graphs.communities.list(
                                    id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1"
                                );
                            }
                            main();
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
                                const response = client.graphs.communities.get(id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1");
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
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to get communities for.",
            ),
            community_ids: Optional[list[UUID]] = Query(
                default=None,
                description="A list of community IDs to filter by.",
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
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to access this community.",
                    403,
                )

            list_communities_response = await self.services[
                "kg"
            ].list_communities_v3(
                graph_id=id,
                filter_community_ids=community_ids,
                filter_user_ids=[auth_user.id],
                offset=offset,
                limit=limit,
            )

            return list_communities_response["results"], {
                "total_entries": list_communities_response["total_entries"],
            }

        @self.router.get(
            "/graphs/{id}/communities/{community_id}",
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

                            result = client.graphs.communities.retrieve(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                community_id="123e4567-e89b-12d3-a456-426614174000"
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
                                const response = client.graphs.communities.retrieve(
                                    id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    community_id="123e4567-e89b-12d3-a456-426614174000"
                                );
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
        ) -> WrappedCommunityResponse:
            """
            Retrieves a specific community by its ID.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to access this community.",
                    403,
                )

            list_communities_response = await self.services[
                "kg"
            ].providers.database.graph_handler.communities.list_communities(
                graph_id=id,
                filter_community_ids=[community_id],
                filter_user_ids=[auth_user.id],
                offset=0,
                limit=1,
            )

            return list_communities_response["results"][0]

        @self.router.delete(
            "/graphs/{id}/communities/{community_id}",
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

                            result = client.graphs.communities.delete(
                                id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                community_id="123e4567-e89b-12d3-a456-426614174000"
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
                                const response = client.graphs.communities.delete(
                                    id="9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                                    community_id="123e4567-e89b-12d3-a456-426614174000"
                                );
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
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to delete the community from.",
            ),
            community_id: UUID = Path(
                ...,
                description="The ID of the community to delete.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Deletes a community from the graph by its ID.
            """

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to delete this community.",
                    403,
                )

            await self.services["kg"].delete_community_v3(
                graph_id=id,
                community_id=community_id,
            )

            return GenericBooleanResponse(success=True)  # type: ignore

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

                            result = client.graphs.communities.update(
                                id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                community_id="123e4567-e89b-12d3-a456-426614174000",
                                name="My Community",
                                summary="A summary of the community",
                                findings=["Finding 1", "Finding 2"],
                                rating=5,
                                rating_explanation="Explanation for the rating",
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
                                const response = client.graphs.communities.update(
                                    id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
                                    community_id="123e4567-e89b-12d3-a456-426614174000",
                                    name="My Community",
                                    summary="A summary of the community",
                                    findings=["Finding 1", "Finding 2"],
                                    rating=5,
                                    rating_explanation="Explanation for the rating",
                                );
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
            id: UUID = Path(...),
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

            if not await self.services["management"].has_graph_access(
                auth_user, id
            ):
                raise R2RException(
                    "You do not have permission to update this community.",
                    403,
                )

            return await self.services["kg"].update_community_v3(
                id=id,
                community_id=community_id,
                name=name,
                summary=summary,
                findings=findings,
                rating=rating,
                rating_explanation=rating_explanation,
                level=level,
                attributes=attributes,
                user_id=auth_user.id,
            )
