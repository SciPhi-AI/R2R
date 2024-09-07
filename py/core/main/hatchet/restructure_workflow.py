import asyncio
import json
import uuid

from hatchet_sdk import Context

from core import GenerationConfig, IngestionStatus, KGCreationSettings

from ..services import RestructureService
from .base import r2r_hatchet
import logging

logger = logging.getLogger(__name__)


@r2r_hatchet.workflow(name="kg-extract-and-store", timeout="60m")
class KgExtractAndStoreWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=3, timeout="60m")
    async def kg_extract_and_store(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]
        print()
        await self.restructure_service.kg_extract_and_store(
            uuid.UUID(input_data["document_id"]),
            GenerationConfig(**input_data["generation_config"]),
        )
        return {"result": None}


@r2r_hatchet.workflow(name="create-graph", timeout="60m")
class CreateGraphWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=1)
    async def kg_extraction_ingress(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]
        kg_creation_settings = KGCreationSettings(
            **json.loads(input_data["kg_creation_settings"])
        )
        document_ids = input_data.get("document_ids", [])

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
                        "kg-extract-and-store",
                        {
                            "request": {
                                "document_id": str(document_id),
                                "generation_config": kg_creation_settings.generation_config.to_dict(),
                            }
                        },
                        key=f"kg-extract-and-store_{document_id}",
                    )
                )
            )

        results = await asyncio.gather(*results)

        return {"result": "success"}


@r2r_hatchet.workflow(name="enrich-graph", timeout="60m")
class EnrichGraphWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=3, timeout="60m")
    async def kg_node_creation(self, context: Context) -> None:
        await self.restructure_service.kg_node_creation()
        return {"result": None}

    @r2r_hatchet.step(retries=3, parents=["kg_node_creation"], timeout="60m")
    async def kg_clustering(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]
        perform_clustering = input_data["perform_clustering"]
        leiden_params = input_data["leiden_params"]
        generation_config = GenerationConfig(**input_data["generation_config"])

        if perform_clustering:
            await self.restructure_service.kg_clustering(
                leiden_params, generation_config, perform_clustering
            )
        else:
            logger.info(
                "Skipping Leiden clustering as perform_clustering is False"
            )

        return {"result": None}
