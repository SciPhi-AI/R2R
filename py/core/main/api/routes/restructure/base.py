from typing import TYPE_CHECKING, Union

from fastapi import Body, Depends

from core.base import KGEnrichmentSettings
from core.main.api.routes.base_router import BaseRouter, RunType

from ....services.restructure_service import RestructureService


class RestructureRouter(BaseRouter):
    def __init__(
        self,
        service: RestructureService,
        run_type: RunType = RunType.RESTRUCTURE,
    ):
        super().__init__(service, run_type)
        self.service: RestructureService = service
        self.setup_routes()

    def setup_routes(self):
        @self.router.post("/enrich_graph")
        @self.base_endpoint
        async def enrich_graph(
            KGEnrichmentSettings: Union[dict, KGEnrichmentSettings] = Body(
                ...,
                description="Settings for knowledge graph enrichment",
            ),
            auth_user=(Depends(self.service.providers.auth.auth_wrapper)),
        ):
            """
            Perform graph enrichment, e.g. GraphRAG, over the ingested documents.

            Returns:
                Dict[str, Any]: Results of the graph enrichment process.
            """
            return await self.service.enrich_graph()
