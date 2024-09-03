from hatchet_sdk import Context
import uuid
from ..services import RestructureService, RestructureServiceAdapter, IngestionService
from .base import r2r_hatchet
from core import IngestionStatus, GenerationConfig
import asyncio


# TODO -
# 1. Add status tracking for each step
# 2. Add error handling for each step
# 3. Add intelligent fan-out across the workflow
# e.g. per document extractions -> chunked node creation -> clustering


@r2r_hatchet.workflow(
    name="kg-extract-and-store", timeout=3600
)
class KgExtractAndStoreWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=3)
    async def kg_extract_and_store(self, context: Context) -> None:
        input_data = context.workflow_input()['request']
        await self.restructure_service.kg_extract_and_store(uuid.UUID(input_data["document_id"]),  GenerationConfig(**input_data["generation_config"]) )
        return {"result": None}

@r2r_hatchet.workflow(
    name="enrich-graph", on_events=["graph:enrich"], timeout=3600
)
class EnrichGraphWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=1)
    async def kg_extraction_ingress(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]
        parsed_data = RestructureServiceAdapter.parse_enrich_graph_input(
            input_data
        )
        kg_enrichment_settings = parsed_data["kg_enrichment_settings"]

        document_ids = kg_enrichment_settings.document_ids

        if not document_ids:
            document_ids = [
                doc.id
                for doc in self.restructure_service.providers.database.relational.get_documents_overview()
                if doc.restructuring_status != IngestionStatus.SUCCESS
            ]

        results = []
        for document_id in document_ids:

            print(f"Spawned workflow for document {document_id}")

            results.append(
                (
                    context.aio.spawn_workflow(
                        "kg-extract-and-store", {"request": {"document_id": str(document_id), "generation_config": kg_enrichment_settings.generation_config_triplet.to_dict()}}, key=f"kg-extract-and-store_{document_id}"
                    )
                )
            )

        results = await asyncio.gather(*results)

        # # clustering_res = await context.aio.spawn_workflow(
        # #     "kg_clustering", {"request": {"leiden_params": kg_enrichment_settings.leiden_params, "generation_config": kg_enrichment_settings.generation_config_enrichment.to_dict()}}, key="kg_clustering"
        # # )

        # print(clustering_res.result())

        return {"result": "success"}

@r2r_hatchet.workflow(
    name="kg_clustering", on_events=["graph:enrich"], timeout=3600
)
class KgClusteringWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=3)
    async def kg_node_creation(self, context: Context) -> None:
        print("kg node extraction ingress2...")
        await self.restructure_service.kg_node_creation()
        return {"result": None}

    @r2r_hatchet.step(retries=3, parents=["kg_node_creation"])
    async def kg_clustering(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]
        leiden_params = input_data["leiden_params"]
        generation_config_enrichment = GenerationConfig(**input_data["generation_config_enrichment"])

        await self.restructure_service.kg_clustering(leiden_params, generation_config_enrichment)
        return {"result": None}
