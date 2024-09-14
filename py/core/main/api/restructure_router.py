import logging
from pathlib import Path
from typing import Optional, Union

import yaml
from fastapi import Body, Depends
from pydantic import Json

from core.base import KGCreationSettings, KGEnrichmentSettings
from core.base.abstractions.document import RestructureStatus
from core.base.api.models.restructure.responses import (
    WrappedKGCreationResponse,
    WrappedKGEnrichmentResponse,
)
from core.base.providers import OrchestrationProvider

from ...main.hatchet import r2r_hatchet
from ..hatchet import (
    CreateGraphWorkflow,
    EnrichGraphWorkflow,
    KGCommunitySummaryWorkflow,
    KgExtractAndStoreWorkflow,
)
from ..services.restructure_service import RestructureService
from .base_router import BaseRouter, RunType

logger = logging.getLogger(__name__)


class RestructureRouter(BaseRouter):
    def __init__(
        self,
        service: RestructureService,
        run_type: RunType = RunType.RESTRUCTURE,
        orchestration_provider: Optional[OrchestrationProvider] = None,
    ):
        if not orchestration_provider:
            raise ValueError(
                "RestructureRouter requires an orchestration provider."
            )
        super().__init__(service, run_type, orchestration_provider)
        self.service: RestructureService = service

        def _load_openapi_extras(self):
            yaml_path = (
                Path(__file__).parent
                / "data"
                / "restructure_router_openapi.yml"
            )
            with open(yaml_path, "r") as yaml_file:
                yaml_content = yaml.safe_load(yaml_file)
            return yaml_content

    def _register_workflows(self):
        self.orchestration_provider.register_workflow(
            EnrichGraphWorkflow(self.service)
        )
        self.orchestration_provider.register_workflow(
            KgExtractAndStoreWorkflow(self.service)
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
            document_ids: Optional[list[str]] = Body(
                default=None,
                description="List of document IDs to create the graph on.",
            ),
            kg_creation_settings: Optional[Json[KGCreationSettings]] = Body(
                default=None,
                description="Settings for the graph creation process.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGCreationResponse:
            """
            Creating a graph on your documents. This endpoint takes input a list of document ids and KGCreationSettings. If document IDs are not provided, the graph will be created on all documents in the system.

            This step extracts the relevant entities and relationships from the documents and creates a graph based on the extracted information. You can view the graph through the neo4j browser.

            In order to do GraphRAG, you will need to run the enrich_graph endpoint.
            """
            # Check if the user is a superuser
            if not auth_user.is_superuser:
                # Add any necessary permission checks here
                pass

            if kg_creation_settings is None:
                kg_creation_settings = (
                    self.service.providers.kg.config.kg_creation_settings
                )

            workflow_input = {
                "document_ids": document_ids,
                "kg_creation_settings": kg_creation_settings.json(),
                "user": auth_user.json(),
            }

            task_id = r2r_hatchet.admin.run_workflow(
                "create-graph", {"request": workflow_input}
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
            skip_clustering: bool = Body(
                default=False,
                description="Whether to skip leiden clustering on the graph or not.",
            ),
            force_enrichment: bool = Body(
                default=False,
                description="Force Enrichment step even if graph creation is still in progress for some documents.",
            ),
            kg_enrichment_settings: Optional[
                Json[KGEnrichmentSettings]
            ] = Body(
                default=None,
                description="Settings for the graph enrichment process.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGEnrichmentResponse:
            """
            This endpoint enriches the graph with additional information. It creates communities of nodes based on their similarity and adds embeddings to the graph. This step is necessary for GraphRAG to work.
            """
            # Check if the user is a superuser
            if not auth_user.is_superuser:
                # Add any necessary permission checks here
                pass

            if kg_enrichment_settings is None:
                kg_enrichment_settings = (
                    self.service.providers.kg.config.kg_enrichment_settings
                )

            workflow_input = {
                "skip_clustering": skip_clustering,
                "force_enrichment": force_enrichment,
                "generation_config": kg_enrichment_settings.generation_config.to_dict(),
                "max_description_input_length": kg_enrichment_settings.max_description_input_length,
                "max_summary_input_length": kg_enrichment_settings.max_summary_input_length,
                "max_description_input_length": kg_enrichment_settings.max_description_input_length,
                "leiden_params": kg_enrichment_settings.leiden_params,
                "user": auth_user.json(),
            }

            task_id = r2r_hatchet.admin.run_workflow(
                "enrich-graph", {"request": workflow_input}
            )

            return {
                "message": "Graph enrichment task queued successfully. Please check http://<your-hatchet-gui-url> for completion status.",
                "task_id": str(task_id),
            }
