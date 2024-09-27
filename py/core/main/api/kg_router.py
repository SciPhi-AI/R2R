import logging
from pathlib import Path
from typing import Optional

import yaml
from fastapi import Body, Depends
from pydantic import Json

from core.base import KGCreationSettings, KGEnrichmentSettings
from core.base.api.models import (
    WrappedKGCreationResponse,
    WrappedKGEnrichmentResponse,
)
from core.base.providers import OrchestrationProvider

from ...main.hatchet import r2r_hatchet
from ..hatchet import (
    CreateGraphWorkflow,
    EnrichGraphWorkflow,
    KGCommunitySummaryWorkflow,
    KgExtractDescribeEmbedWorkflow,
)
from ..services.kg_service import KgService
from .base_router import BaseRouter, RunType

logger = logging.getLogger(__name__)


class KGRouter(BaseRouter):
    def __init__(
        self,
        service: KgService,
        run_type: RunType = RunType.KG,
        orchestration_provider: Optional[OrchestrationProvider] = None,
    ):
        if not orchestration_provider:
            raise ValueError("KGRouter requires an orchestration provider.")
        super().__init__(service, run_type, orchestration_provider)
        self.service: KgService = service

    def _load_openapi_extras(self):
        yaml_path = Path(__file__).parent / "data" / "kg_router_openapi.yml"
        with open(yaml_path, "r") as yaml_file:
            yaml_content = yaml.safe_load(yaml_file)
        return yaml_content

    def _register_workflows(self):
        self.orchestration_provider.register_workflow(
            KgExtractDescribeEmbedWorkflow(self.service)
        )
        self.orchestration_provider.register_workflow(
            CreateGraphWorkflow(self.service)
        )
        self.orchestration_provider.register_workflow(
            KGCommunitySummaryWorkflow(self.service)
        )

    def _setup_routes(self):
        @self.router.post(
            "/create_graph",
        )
        @self.base_endpoint
        async def create_graph(
            project_name: str = Body(
                description="Project name to create graph for.",
            ),
            collection_id: str = Body(
                description="Collection ID to create graph for.",
            ),
            kg_creation_settings: Optional[Json[KGCreationSettings]] = Body(
                default=None,
                description="Settings for the graph creation process.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
            response_model=WrappedKGCreationResponse,
        ):
            """
            Creating a graph on your documents. This endpoint takes input a list of document ids and KGCreationSettings. If document IDs are not provided, the graph will be created on all documents in the system.

            This step extracts the relevant entities and relationships from the documents and creates a graph based on the extracted information. You can view the graph through the neo4j browser.

            In order to do GraphRAG, you will need to run the enrich_graph endpoint.
            """

            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if kg_creation_settings is None:
                kg_creation_settings = (
                    self.service.providers.kg.config.kg_creation_settings
                )

            task_id = r2r_hatchet.admin.run_workflow(
                "create-graph",
                {
                    "request": {
                        "project_name": project_name,
                        "collection_id": collection_id,
                        "kg_creation_settings": kg_creation_settings.json(),
                        "user": auth_user.json(),
                    }
                },
            )

            return {
                "message": f"Graph creation task queued successfully. Please check http://<your-hatchet-gui-url> for completion status.",
                "task_id": str(task_id),
            }

        @self.router.post(
            "/enrich_graph",
        )
        @self.base_endpoint
        async def enrich_graph(
            project_name: str = Body(
                description="Project name to enrich graph for.",
            ),
            collection_id: str = Body(
                description="Collection name to enrich graph for.",
            ),
            kg_enrichment_settings: Optional[
                Json[KGEnrichmentSettings]
            ] = Body(
                default=None,
                description="Settings for the graph enrichment process.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
            response_model=WrappedKGEnrichmentResponse,
        ):
            """
            This endpoint enriches the graph with additional information. It creates communities of nodes based on their similarity and adds embeddings to the graph. This step is necessary for GraphRAG to work.
            """

            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if kg_enrichment_settings is None:
                kg_enrichment_settings = (
                    self.service.providers.kg.config.kg_enrichment_settings
                )

            workflow_input = {
                "project_name": project_name,
                "collection_id": collection_id,
                "kg_enrichment_settings": kg_enrichment_settings.json(),
                "user": auth_user.json(),
            }

            task_id = r2r_hatchet.admin.run_workflow(
                "enrich-graph", {"request": workflow_input}
            )

            return {
                "message": "Graph enrichment task queued successfully. Please check http://<your-hatchet-gui-url> for completion status.",
                "task_id": str(task_id),
            }
