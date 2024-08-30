import logging
from pathlib import Path
from typing import Optional

import yaml
from fastapi import Body, Depends
from pydantic import Json

from core.base import KGEnrichmentSettings
from core.base.api.models.restructure.responses import (
    WrappedKGEnrichmentResponse,
)
from core.base.providers import OrchestrationProvider

from ...main.hatchet import r2r_hatchet
from ..hatchet import EnrichGraphWorkflow
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

    def _register_workflows(self):
        self.orchestration_provider.register_workflow(
            EnrichGraphWorkflow(self.service)
        )

    def _setup_routes(self):
        @self.router.post(
            "/enrich_graph",
        )
        @self.base_endpoint
        async def enrich_graph(
            kg_enrichment_settings: Json[KGEnrichmentSettings] = Body(
                ...,
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGEnrichmentResponse:
            """
            Perform graph enrichment, e.g. GraphRAG, over the ingested documents.

            This endpoint supports JSON requests, enabling you to enrich the knowledge graph in R2R.

            A valid user authentication token is required to access this endpoint.
            """
            # Check if the user is a superuser
            is_superuser = auth_user and auth_user.is_superuser

            if not is_superuser:
                # Add any necessary permission checks here
                pass

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
