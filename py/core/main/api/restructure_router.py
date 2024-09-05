import logging
from typing import Optional

from pathlib import Path
import yaml

from fastapi import Body, Depends
from pydantic import Json

from core.base import KGCreationSettings, KGEnrichmentSettings
from core.base.api.models.restructure.responses import (
    WrappedKGEnrichmentResponse,
)
from core.base.providers import OrchestrationProvider

from ...main.hatchet import r2r_hatchet
from ..hatchet import (
    CreateGraphWorkflow,
    EnrichGraphWorkflow,
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
                Path(__file__).parent / "data" / "restructure_router_openapi.yml"
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

    def _setup_routes(self):
        @self.router.post(
            "/create_graph",
        )
        @self.base_endpoint
        async def create_graph(
            document_ids: Optional[list[str]],
            kg_creation_settings: Json[KGCreationSettings] = Body(
                default_factory=KGCreationSettings
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGEnrichmentResponse:
            """
                Creating a graph on your documents. This endpoint takes input a list of document ids and KGCreationSettings. If document IDs are not provided, the graph will be created on all documents in the system.

                This step extracts the relevant entities and relationships from the documents and creates a graph based on the extracted information. You can view the graph through the neo4j browser.

                In order to do GraphRAG, you will need to run the enrich_graph endpoint.
            """
            # Check if the user is a superuser
            is_superuser = auth_user and auth_user.is_superuser

            if not is_superuser:
                # Add any necessary permission checks here
                pass

            workflow_input = {
                "document_ids": document_ids,
                "kg_creation_settings": kg_creation_settings.json(),
                "user": auth_user.json(),
            }

            task_id = r2r_hatchet.client.admin.run_workflow(
                "create-graph", {"request": workflow_input}
            )

            return {
                "message": "Graph creation task queued successfully.",
                "task_id": str(task_id),
            }

        @self.router.post(
            "/enrich_graph",
        )
        @self.base_endpoint
        async def enrich_graph(
            kg_enrichment_settings: Json[KGEnrichmentSettings] = Body(
                default_factory=KGEnrichmentSettings
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGEnrichmentResponse:
            """
                This endpoint enriches the graph with additional information. It creates communities of nodes based on their similarity and adds embeddings to the graph. This step is necessary for GraphRAG to work.
            """
            # Check if the user is a superuser
            is_superuser = auth_user and auth_user.is_superuser

            if not is_superuser:
                # Add any necessary permission checks here
                pass

            workflow_input = {
                "generation_config": kg_enrichment_settings.generation_config.to_dict(),
                "leiden_params": kg_enrichment_settings.leiden_params,
                "user": auth_user.json(),
            }

            task_id = r2r_hatchet.client.admin.run_workflow(
                "enrich-graph", {"request": workflow_input}
            )

            return {
                "message": "Graph enrichment task queued successfully.",
                "task_id": str(task_id),
            }
