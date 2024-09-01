from hatchet_sdk import Context

from ..services import RestructureService, RestructureServiceAdapter
from .base import r2r_hatchet

# TODO - 
# 1. Add status tracking for each step
# 2. Add error handling for each step
# 3. Add intelligent fan-out across the workflow
# e.g. per document extractions -> chunked node creation -> clustering
@r2r_hatchet.workflow(
    name="enrich-graph", on_events=["graph:enrich"], timeout=3600
)
class EnrichGraphWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=3)
    async def kg_extract_and_store(self, context: Context) -> None:
        print("extract and score ingress...")

        input_data = context.workflow_input()["request"]
        parsed_data = RestructureServiceAdapter.parse_enrich_graph_input(
            input_data
        )
        kg_enrichment_settings = parsed_data["kg_enrichment_settings"]

        async def input_generator():
            input = []
            for doc in input:
                yield doc

        results = await self.restructure_service.kg_extract_and_store(
            input_generator, kg_enrichment_settings
        )
        print("extract and score results = ", results)
        return {"result": results}

    @r2r_hatchet.step(retries=3, parents=["kg_extract_and_store"])
    async def kg_node_creation(self, context: Context) -> None:
        print("kg node extraction ingress...")
        prev_step = context.step_output("kg_extract_and_store")
        await self.restructure_service.kg_node_creation(prev_step["result"])
        return {"result": None}

    @r2r_hatchet.step(retries=3, parents=["kg_node_creation"])
    async def kg_clustering(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]
        parsed_data = RestructureServiceAdapter.parse_enrich_graph_input(
            input_data
        )
        kg_enrichment_settings = parsed_data["kg_enrichment_settings"]

        await self.restructure_service.kg_clustering(
            kg_enrichment_settings
        )
        return {"result": None}