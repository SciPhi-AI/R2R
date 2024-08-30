from typing import TYPE_CHECKING, Optional, Union

from fastapi import Body, Depends

from core.base import KGEnrichmentSettings
from core.base.api.models.restructure.responses import (
    WrappedKGEnrichmentResponse,
)
from core.base.providers import OrchestrationProvider

from ...main.hatchet import EnrichGraphWorkflow, r2r_hatchet
from ..services.restructure_service import RestructureService
from .base_router import BaseRouter, RunType


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
        self.service: RestructureService = service  # for type hinting

    def _register_workflows(self):
        self.orchestration_provider.register_workflow(
            EnrichGraphWorkflow(self.service)
        )

    def _setup_routes(self):
        @self.router.post("/enrich_graph")
        @self.base_endpoint
        async def enrich_graph(
            kg_enrichment_settings: KGEnrichmentSettings = Body(
                ...,
                description="Settings for knowledge graph enrichment",
            ),
            auth_user=(Depends(self.service.providers.auth.auth_wrapper)),
        ) -> WrappedKGEnrichmentResponse:
            """
            Perform graph enrichment, e.g. GraphRAG, over the ingested documents.

            Returns:
                Dict[str, Any]: Results of the graph enrichment process.
            """
            workflow_input = {
                "kg_enrichment_settings": kg_enrichment_settings.json(),
                "user": auth_user.json(),
            }

            task_id = r2r_hatchet.client.admin.run_workflow(
                "enrich-graph", {"request": workflow_input}
            )

            return {
                "message": "Graph enrichment task queued successfully.",
                "task_id": str(task_id),
            }
