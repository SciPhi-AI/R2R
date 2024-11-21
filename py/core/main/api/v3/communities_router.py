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

            return await self._create_communities(
                graph_id=id,
                settings=settings,
                run_type=run_type,
                run_with_orchestration=run_with_orchestration,
                auth_user=auth_user,
            )

        @self.router.post(
            "/communities",
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
            communities: list[Community] = Body(
                ..., description="The communities to create."
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Creates custom communities in the graph.

            While communities are typically built automatically via the /graphs/{id}/communities/build endpoint,
            this endpoint allows you to manually create your own communities. This can be useful when you want to:

            - Define custom groupings of entities based on domain knowledge
            - Add communities that weren't detected by the automatic process
            - Create hierarchical organization structures
            - Tag groups of entities with specific metadata

            The created communities will be integrated with any existing automatically detected communities
            in the graph's community structure.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            return await self.services["kg"].create_communities_v3(communities)

        @self.router.get(
            "/communities",
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
            id: UUID = Query(
                ...,
                description="The ID of the graph to get communities for.",
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
            attributes: Optional[list[str]] = Query(
                None,
                description="A list of attributes to return. By default, all attributes are returned.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Lists all communities in the graph with pagination support.

            By default, all attributes are returned, but this can be limited using the `attributes` parameter.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            communities, count = await self.services[
                "kg"
            ].providers.database.graph_handler.communities.get(
                id=id,
                offset=offset,
                limit=limit,
                attributes=attributes,
            )

            return communities, {
                "total_entries": count,
            }

        @self.router.get(
            "/communities/{id}",
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
            """
            Retrieves a specific community by its ID.

            By default, all attributes are returned, but this can be limited using the `attributes` parameter.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )

            return await self.services[
                "kg"
            ].providers.database.graph_handler.communities.get(
                community_id=id,
                attributes=attributes,
            )

        @self.router.delete(
            "/communities/{id}",
            summary="Delete a community",
        )
        @self.base_endpoint
        async def delete_community(
            request: Request,
            id: UUID = Path(
                ...,
                description="The ID of the graph to delete the community from.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can access this endpoint.", 403
                )
            return await self.services["kg"].delete_community_v3(
                id=id,
            )

        @self.router.post(
            "/communities/{id}",
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
                                id="d09dedb1-b2ab-48a5-b950-6e1f464d83e7",
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
            community: Community = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            """
            Updates an existing community's metadata and properties.
            """
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only superusers can update communities", 403
                )

            return await self.services[
                "kg"
            ].providers.database.graph_handler.communities.update(community)
