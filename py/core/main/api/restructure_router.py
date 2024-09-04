import logging
from typing import Optional

from fastapi import Body, Depends
from pydantic import Json

from core.base import KGCreationSettings, KGEnrichmentSettings
from core.base.api.models.restructure.responses import (
    WrappedKGEnrichmentResponse,
)
from core.base.providers import OrchestrationProvider

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
            Input:
            - document_ids: list[str], optional, if not provided, all documents will be used
            - kg_creation_settings: KGCreationSettings
            - auth_user: AuthUser

            This endpoint supports JSON requests, enabling you to create a new knowledge graph in R2R.

            A valid user authentication token is required to access this endpoint.
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

            task_id = self.orchestration_provider.workflow(
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
            Input:
            - kg_enrichment_settings: KGEnrichmentSettings
            - auth_user: AuthUser

            Perform graph enrichment, over the entire graph.

            This endpoint supports JSON requests, enabling you to enrich the knowledge graph in R2R.

            A valid user authentication token is required to access this endpoint.
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

            task_id = self.orchestration_provider.workflow(
                "enrich-graph", {"request": workflow_input}
            )

            return {
                "message": "Graph enrichment task queued successfully.",
                "task_id": str(task_id),
            }
