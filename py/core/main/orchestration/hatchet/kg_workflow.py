import asyncio
import json
import logging
import math
import uuid

from hatchet_sdk import Context, ConcurrencyLimitStrategy

from core import GenerationConfig
from core.base import OrchestrationProvider

from ...services import KgService

logger = logging.getLogger(__name__)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hatchet_sdk import Hatchet


def hatchet_kg_factory(
    orchestration_provider: OrchestrationProvider, service: KgService
) -> dict[str, "Hatchet.Workflow"]:

    def get_input_data_dict(input_data):
        for key, value in input_data.items():
            if key == "kg_creation_settings":
                input_data[key] = json.loads(value)
                input_data[key]["generation_config"] = GenerationConfig(
                    **input_data[key]["generation_config"]
                )
            if key == "kg_enrichment_settings":
                input_data[key] = json.loads(value)

            if key == "generation_config":
                input_data[key] = GenerationConfig(**input_data[key])
        return input_data

    @orchestration_provider.workflow(name="kg-extract", timeout="360m")
    class KGExtractDescribeEmbedWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.concurrency(
            max_runs=orchestration_provider.config.kg_creation_concurrency_limit,
            limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
        )
        def concurrency(self, context) -> str:
            return str(context.workflow_input()["request"]["collection_id"])

        @orchestration_provider.step(retries=1, timeout="360m")
        async def kg_extract(self, context: Context) -> dict:

            context.log(
                f"Running KG Extraction for input: {context.workflow_input()['request']}"
            )

            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )

            # context.log(f"Running KG Extraction for collection ID: {input_data['collection_id']}")
            document_id = input_data["document_id"]

            await self.kg_service.kg_triples_extraction(
                document_id=uuid.UUID(document_id),
                logger=context.log,
                **input_data["kg_creation_settings"],
            )

            return {
                "result": f"successfully ran kg triples extraction for document {document_id}"
            }

        @orchestration_provider.step(
            retries=1, timeout="360m", parents=["kg_extract"]
        )
        async def kg_entity_description(self, context: Context) -> dict:

            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )
            document_id = input_data["document_id"]

            await self.kg_service.kg_entity_description(
                document_id=uuid.UUID(document_id),
                **input_data["kg_creation_settings"],
            )

            return {
                "result": f"successfully ran kg node description for document {document_id}"
            }

    @orchestration_provider.workflow(name="create-graph", timeout="360m")
    class CreateGraphWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=1)
        async def get_document_ids_for_create_graph(
            self, context: Context
        ) -> dict:

            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )
            collection_id = input_data["collection_id"]

            return_val = {
                "document_ids": [
                    str(doc_id)
                    for doc_id in await self.kg_service.get_document_ids_for_create_graph(
                        collection_id=collection_id,
                        **input_data["kg_creation_settings"],
                    )
                ]
            }

            if len(return_val["document_ids"]) == 0:
                raise ValueError(
                    "No documents to process, either all documents to create the graph were already created or in progress, or the collection is empty."
                )

            return return_val

        @orchestration_provider.step(
            retries=1, parents=["get_document_ids_for_create_graph"]
        )
        async def kg_extraction_ingress(self, context: Context) -> dict:

            document_ids = [
                uuid.UUID(doc_id)
                for doc_id in context.step_output(
                    "get_document_ids_for_create_graph"
                )["document_ids"]
            ]
            results = []
            for cnt, document_id in enumerate(document_ids):
                context.log(
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
                                    "collection_id": context.workflow_input()[
                                        "request"
                                    ]["collection_id"],
                                }
                            },
                            key=f"kg-extract-{cnt}/{len(document_ids)}",
                        )
                    )
                )

            if not document_ids:
                context.log(
                    "No documents to process, either all graphs were created or in progress, or no documents were provided. Skipping graph creation."
                )
                return {"result": "No documents to process"}

            context.log(f"Ran {len(results)} workflows for graph creation")
            results = await asyncio.gather(*results)
            return {
                "result": f"successfully ran graph creation workflows for {len(results)} documents"
            }

    @orchestration_provider.workflow(name="enrich-graph", timeout="360m")
    class EnrichGraphWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=1, parents=[], timeout="360m")
        async def kg_clustering(self, context: Context) -> dict:

            logger.info("Running KG Clustering")
            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )
            collection_id = input_data["collection_id"]

            kg_clustering_results = await self.kg_service.kg_clustering(
                collection_id=collection_id,
                **input_data["kg_enrichment_settings"],
            )

            context.log(
                f"Successfully ran kg clustering for collection {collection_id}: {json.dumps(kg_clustering_results)}"
            )
            logger.info(
                f"Successfully ran kg clustering for collection {collection_id}: {json.dumps(kg_clustering_results)}"
            )

            return {
                "result": f"successfully ran kg clustering for collection {collection_id}",
                "kg_clustering": kg_clustering_results,
            }

        @orchestration_provider.step(retries=1, parents=["kg_clustering"])
        async def kg_community_summary(self, context: Context) -> dict:

            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )
            collection_id = input_data["collection_id"]
            num_communities = context.step_output("kg_clustering")[
                "kg_clustering"
            ][0]["num_communities"]

            parallel_communities = min(100, num_communities)
            total_workflows = math.ceil(num_communities / parallel_communities)
            workflows = []
            for i in range(total_workflows):
                offset = i * parallel_communities
                workflows.append(
                    context.aio.spawn_workflow(
                        "kg-community-summary",
                        {
                            "request": {
                                "offset": offset,
                                "limit": min(
                                    parallel_communities,
                                    num_communities - offset,
                                ),
                                "collection_id": collection_id,
                                **input_data["kg_enrichment_settings"],
                            }
                        },
                        key=f"{i}/{total_workflows}_community_summary",
                    )
                )
            await asyncio.gather(*workflows)
            return {
                "result": f"Successfully spawned summary workflows for {num_communities} communities."
            }

    @orchestration_provider.workflow(
        name="kg-community-summary", timeout="360m"
    )
    class KGCommunitySummaryWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=1, timeout="360m")
        async def kg_community_summary(self, context: Context) -> dict:
            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )

            community_summary = await self.kg_service.kg_community_summary(
                **input_data
            )
            context.log(
                f"Successfully ran kg community summary for communities {input_data['offset']} to {input_data['offset'] + len(community_summary)}"
            )
            return {
                "result": f"successfully ran kg community summary for communities {input_data['offset']} to {input_data['offset'] + len(community_summary)}"
            }

    return {
        "kg-extract": KGExtractDescribeEmbedWorkflow(service),
        "create-graph": CreateGraphWorkflow(service),
        "enrich-graph": EnrichGraphWorkflow(service),
        "kg-community-summary": KGCommunitySummaryWorkflow(service),
    }
