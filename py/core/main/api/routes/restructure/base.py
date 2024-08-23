from typing import Union

from fastapi import Body, Depends

from core.base import KGEnrichmentSettings
from core.main.api.routes.base_router import BaseRouter, RunType
from core.main.engine import R2REngine


class RestructureRouter(BaseRouter):
    def __init__(
        self, engine: R2REngine, run_type: RunType = RunType.RESTRUCTURE
    ):
        super().__init__(engine, run_type)
        self.setup_routes()

    def setup_routes(self):
        @self.router.post("/enrich_graph")
        @self.base_endpoint
        async def enrich_graph(
            KGEnrichmentSettings: Union[dict, KGEnrichmentSettings] = Body(
                ...,
                description="Settings for knowledge graph enrichment",
            ),
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            """
            Perform graph enrichment, e.g. GraphRAG, over the ingested documents.

            Returns:
                Dict[str, Any]: Results of the graph enrichment process.
            """
            return await self.engine.aenrich_graph()
