from hatchet_sdk import Context

from ..services import RestructureService, RestructureServiceAdapter
from .base import r2r_hatchet
from core.base import KGExtraction, Entity

@r2r_hatchet.workflow(
    name="enrich-graph", on_events=["graph:enrich"], timeout=3600
)
class EnrichGraphWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=3)
    async def kg_extract_and_store(self, context: Context) -> None:
        print('extract and score ingress...')

        input_data = context.workflow_input()["request"]
        parsed_data = RestructureServiceAdapter.parse_enrich_graph_input(input_data)
        kg_enrichment_settings = parsed_data["kg_enrichment_settings"]

        async def input_generator():
            input = []
            for doc in input:
                yield doc

        results = await self.restructure_service.kg_extract_and_store(input_generator, kg_enrichment_settings)
        print('extract and score results = ', results)
        return {"result": results}

    @r2r_hatchet.step(retries=3, parents=["kg_extract_and_store"])
    async def kg_node_creation(self, context: Context) -> None:
        print('kg node extraction ingress...')
        prev_step = context.step_output("kg_extract_and_store")
        # Nodes are not explicitly needed
        await self.restructure_service.kg_node_creation(prev_step["result"])
        # print('node extraction nodes = ', nodes)
        return {"result": None}

    # @r2r_hatchet.step(retries=3, parents=["kg_node_extraction"])
    # async def kg_node_description(self, context: Context) -> None:
    #     prev_step = context.step_output("kg_node_extraction")
    #     descriptions = await self.restructure_service.kg_node_description(prev_step["result"])
    #     return {"result": descriptions}

    @r2r_hatchet.step(retries=3, parents=["kg_node_creation"])
    async def kg_clustering(self, context: Context) -> None:
        # prev_step = context.step_output("kg_node_creation")
        input_data = context.workflow_input()["request"]
        # print('entity = ', prev_step["result"][0])
        # entities = [Entity.from_json(entity) for entity in prev_step["result"]]
        parsed_data = RestructureServiceAdapter.parse_enrich_graph_input(input_data)
        kg_enrichment_settings = parsed_data["kg_enrichment_settings"]
    
        clusters = await self.restructure_service.kg_clustering(kg_enrichment_settings)
        return {"result": clusters}

    # @r2r_hatchet.step(retries=3, parents=["kg_clustering"])
    # async def finalize_enrichment(self, context: Context) -> None:
    #     prev_step = context.step_output("kg_clustering")
    #     clusters = prev_step["result"]

    #     # Process the clusters as needed
    #     result = []
    #     async for cluster in clusters:
    #         result.append(cluster)

    #     return {"result": result}        # storage = await self.restructure_service.kg_s/torage(triples)
