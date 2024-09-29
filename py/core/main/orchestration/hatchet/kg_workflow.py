import asyncio
import json
import logging
import uuid
import math

from hatchet_sdk import Context

from core import GenerationConfig, IngestionStatus, KGCreationSettings
from core.base import OrchestrationProvider, R2RDocumentProcessingError
from core.base.abstractions import KGCreationStatus, KGEnrichmentStatus

from ...services import KgService

logger = logging.getLogger(__name__)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hatchet_sdk import Hatchet


def hatchet_kg_factory(
    orchestration_provider: OrchestrationProvider, service: KgService
) -> list["Hatchet.Workflow"]:

    @orchestration_provider.workflow(name="kg-extract", timeout="360m")
    class KGExtractDescribeEmbedWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=3, timeout="360m")
        async def kg_extract(self, context: Context) -> dict:
            return await self.kg_service.kg_extract_and_store(
                **context.workflow_input()["request"]
            )

        @orchestration_provider.step(retries=3, timeout="360m")
        async def kg_node_description(self, context: Context) -> dict:
            return await self.kg_service.kg_node_description(
                **context.workflow_input()["request"]
            )

    @orchestration_provider.workflow(name="create-graph", timeout="60m")
    class CreateGraphWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=1)
        async def get_document_ids_for_create_graph(
            self, context: Context
        ) -> dict:
            return await self.kg_service.get_document_ids_for_create_graph(
                **context.workflow_input()["request"]
            )

        @orchestration_provider.step(
            retries=1, parents=["get_document_ids_for_create_graph"]
        )
        async def kg_extraction_ingress(self, context: Context) -> dict:

            document_ids = context.step_output(
                "get_document_ids_for_create_graph"
            )
            results = []
            for cnt, document_id in enumerate(document_ids):
                context.logger.info(
                    f"Running Graph Creation Workflow for document ID: {document_id}"
                )
                results.append(
                    (
                        context.aio.spawn_workflow(
                            "kg-extract",
                            {
                                "request": {
                                    "document_id": str(document_id),
                                    "kg_creation_settings": context.workflow_input()[
                                        "request"
                                    ][
                                        "kg_creation_settings"
                                    ],
                                }
                            },
                            key=f"kg-extract-{cnt}/{len(document_ids)}",
                        )
                    )
                )

            if not document_ids:
                logger.info(
                    "No documents to process, either all graphs were created or in progress, or no documents were provided. Skipping graph creation."
                )
                return {"result": "No documents to process"}

            logger.info(f"Ran {len(results)} workflows for graph creation")
            results = await asyncio.gather(*results)
            return {
                "result": f"successfully ran graph creation workflows for {len(results)} documents"
            }

    @orchestration_provider.workflow(name="enrich-graph", timeout="60m")
    class EnrichGraphWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=1, parents=[], timeout="360m")
        async def kg_clustering(self, context: Context) -> dict:
            return await self.kg_service.kg_clustering(
                **context.workflow_input()["request"]
            )

        @orchestration_provider.step(retries=1, parents=["kg_clustering"])
        async def kg_community_summary(self, context: Context) -> dict:

            input_data = context.workflow_input()["request"]
            num_communities = context.step_output("kg_clustering")[0][
                "num_communities"
            ]

            parallel_communities = min(100, num_communities)
            total_workflows = math.ceil(num_communities / parallel_communities)
            workflows = []
            for i, offset in enumerate(
                range(0, num_communities, parallel_communities)
            ):
                workflows.append(
                    context.aio.spawn_workflow(
                        "kg-community-summary",
                        {
                            "request": {
                                "offset": offset,
                                "limit": parallel_communities,
                                **input_data,
                            }
                        },
                        key=f"{i}/{total_workflows}_community_summary",
                    )
                )
            await asyncio.gather(*workflows)
            return {
                "result": "successfully ran kg community summary workflows"
            }

    @orchestration_provider.workflow(
        name="kg-community-summary", timeout="60m"
    )
    class KGCommunitySummaryWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=1, timeout="60m")
        async def kg_community_summary(self, context: Context) -> dict:
            return await self.kg_service.kg_community_summary(
                **context.workflow_input()["request"]
            )

    return {
        "kg-extract": KGExtractDescribeEmbedWorkflow(service),
        "create-graph": CreateGraphWorkflow(service),
        "enrich-graph": EnrichGraphWorkflow(service),
        "kg-community-summary": KGCommunitySummaryWorkflow(service),
    }
