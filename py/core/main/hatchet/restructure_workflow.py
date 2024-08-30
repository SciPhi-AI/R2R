from hatchet_sdk import Context

from ..services import RestructureService, RestructureServiceAdapter
from .base import r2r_hatchet


@r2r_hatchet.workflow(
    name="enrich-graph", on_events=["graph:enrich"], timeout=3600
)
class EnrichGraphWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=0)
    async def enrich_graph(self, context: Context) -> None:
        data = context.workflow_input()["request"]

        parsed_data = RestructureServiceAdapter.parse_enrich_graph_input(data)

        await self.restructure_service.enrich_graph(**parsed_data)
