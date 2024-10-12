import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

import yaml
from fastapi import Body, Depends, Query

from core.base import RunType
from core.base.api.models import (
    WrappedKGCreationResponse,
    WrappedKGEnrichmentResponse,
    WrappedKGEntitiesResponse,
    WrappedKGTriplesResponse,
    WrappedKGCommunitiesResponse,
)
from core.base.providers import OrchestrationProvider, Workflow
from core.utils import generate_default_user_collection_id
from shared.abstractions.kg import KGRunType
from shared.utils.base_utils import update_settings_from_dict
from ..services.kg_service import KgService
from .base_router import BaseRouter

logger = logging.getLogger(__name__)


class KGRouter(BaseRouter):
    def __init__(
        self,
        service: KgService,
        orchestration_provider: Optional[OrchestrationProvider] = None,
        run_type: RunType = RunType.KG,
    ):
        if not orchestration_provider:
            raise ValueError("KGRouter requires an orchestration provider.")
        super().__init__(service, orchestration_provider, run_type)
        self.service: KgService = service

    def _load_openapi_extras(self):
        yaml_path = Path(__file__).parent / "data" / "kg_router_openapi.yml"
        with open(yaml_path, "r") as yaml_file:
            yaml_content = yaml.safe_load(yaml_file)
        return yaml_content

    def _register_workflows(self):

        workflow_messages = {}
        if self.orchestration_provider.config.provider == "hatchet":
            workflow_messages["create-graph"] = (
                "Graph creation task queued successfully."
            )
            workflow_messages["enrich-graph"] = (
                "Graph enrichment task queued successfully."
            )
        else:
            workflow_messages["create-graph"] = (
                "Graph created successfully, please run enrich-graph to enrich the graph for GraphRAG."
            )
            workflow_messages["enrich-graph"] = "Graph enriched successfully."

        self.orchestration_provider.register_workflows(
            Workflow.KG,
            self.service,
            workflow_messages,
        )

    def _setup_routes(self):
        @self.router.post(
            "/create_graph",
        )
        @self.base_endpoint
        async def create_graph(
            collection_id: Optional[UUID] = Body(
                default=None,
                description="Collection ID to create graph for.",
            ),
            run_type: Optional[KGRunType] = Body(
                default=None,
                description="Run type for the graph creation process.",
            ),
            kg_creation_settings: Optional[dict] = Body(
                default=None,
                description="Settings for the graph creation process.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGCreationResponse:  # type: ignore
            """
            Creating a graph on your documents. This endpoint takes input a list of document ids and KGCreationSettings.
            If document IDs are not provided, the graph will be created on all documents in the system.
            This step extracts the relevant entities and relationships from the documents and creates a graph based on the extracted information.
            In order to do GraphRAG, you will need to run the enrich_graph endpoint.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            logger.info(f"Running create-graph on collection {collection_id}")

            # If no collection ID is provided, use the default user collection
            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            # If no run type is provided, default to estimate
            if not run_type:
                run_type = KGRunType.ESTIMATE

            # Apply runtime settings overrides
            server_kg_creation_settings = (
                self.service.providers.kg.config.kg_creation_settings
            )

            if kg_creation_settings:
                server_kg_creation_settings = update_settings_from_dict(
                    server_kg_creation_settings, kg_creation_settings
                )

            # If the run type is estimate, return an estimate of the creation cost
            if run_type is KGRunType.ESTIMATE:
                return await self.service.get_creation_estimate(
                    collection_id, server_kg_creation_settings
                )

            # Otherwise, create the graph
            else:
                workflow_input = {
                    "collection_id": str(collection_id),
                    "kg_creation_settings": server_kg_creation_settings.model_dump_json(),
                    "user": auth_user.json(),
                }

                return await self.orchestration_provider.run_workflow(  # type: ignore
                    "create-graph", {"request": workflow_input}, {}
                )

        @self.router.post(
            "/enrich_graph",
        )
        @self.base_endpoint
        async def enrich_graph(
            collection_id: Optional[UUID] = Body(
                default=None,
                description="Collection ID to enrich graph for.",
            ),
            run_type: Optional[KGRunType] = Body(
                default=KGRunType.ESTIMATE,
                description="Run type for the graph enrichment process.",
            ),
            kg_enrichment_settings: Optional[dict] = Body(
                default=None,
                description="Settings for the graph enrichment process.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGEnrichmentResponse:
            """
            This endpoint enriches the graph with additional information.
            It creates communities of nodes based on their similarity and adds embeddings to the graph.
            This step is necessary for GraphRAG to work.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            # If no collection ID is provided, use the default user collection
            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            # If no run type is provided, default to estimate
            if not run_type:
                run_type = KGRunType.ESTIMATE

            # Apply runtime settings overrides
            server_kg_enrichment_settings = (
                self.service.providers.kg.config.kg_enrichment_settings
            )
            if kg_enrichment_settings:
                server_kg_enrichment_settings = update_settings_from_dict(
                    server_kg_enrichment_settings, kg_enrichment_settings
                )

            # If the run type is estimate, return an estimate of the enrichment cost
            if run_type is KGRunType.ESTIMATE:
                return await self.service.get_enrichment_estimate(
                    collection_id, server_kg_enrichment_settings
                )

            # Otherwise, run the enrichment workflow
            else:
                workflow_input = {
                    "collection_id": str(collection_id),
                    "kg_enrichment_settings": server_kg_enrichment_settings.model_dump_json(),
                    "user": auth_user.json(),
                }

                return await self.orchestration_provider.run_workflow(  # type: ignore
                    "enrich-graph", {"request": workflow_input}, {}
                )

        @self.router.get("/entities")
        @self.base_endpoint
        async def get_entities(
            collection_id: Optional[UUID] = Query(
                None, description="Collection ID to retrieve entities from."
            ),
            offset: int = Query(0, ge=0, description="Offset for pagination."),
            limit: int = Query(
                100, ge=1, le=1000, description="Limit for pagination."
            ),
            entity_ids: Optional[list[str]] = Query(
                None, description="Entity IDs to filter by."
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGEntitiesResponse:
            """
            Retrieve entities from the knowledge graph.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            return await self.service.get_entities(
                collection_id,
                offset,
                limit,
                entity_ids,
            )

        @self.router.get("/triples")
        @self.base_endpoint
        async def get_triples(
            collection_id: Optional[UUID] = Query(
                None, description="Collection ID to retrieve triples from."
            ),
            offset: int = Query(0, ge=0, description="Offset for pagination."),
            limit: int = Query(
                100, ge=1, le=1000, description="Limit for pagination."
            ),
            entity_names: Optional[list[str]] = Query(
                None, description="Entity names to filter by."
            ),
            triple_ids: Optional[list[str]] = Query(
                None, description="Triple IDs to filter by."
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGTriplesResponse:
            """
            Retrieve triples from the knowledge graph.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            return await self.service.get_triples(
                collection_id,
                offset,
                limit,
                entity_names,
                triple_ids,
            )

        @self.router.get("/communities")
        @self.base_endpoint
        async def get_communities(
            collection_id: Optional[UUID] = Query(
                None, description="Collection ID to retrieve communities from."
            ),
            offset: int = Query(0, ge=0, description="Offset for pagination."),
            limit: int = Query(
                100, ge=1, le=1000, description="Limit for pagination."
            ),
            levels: Optional[list[int]] = Query(
                None, description="Levels to filter by."
            ),
            community_numbers: Optional[list[int]] = Query(
                None, description="Community numbers to filter by."
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGCommunitiesResponse:
            """
            Retrieve communities from the knowledge graph.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            return await self.service.get_communities(
                collection_id,
                offset,
                limit,
                levels,
                community_numbers,
            )
