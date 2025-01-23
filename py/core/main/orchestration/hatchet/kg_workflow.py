import asyncio
import contextlib
import json
import logging
import math
import time
import uuid

from hatchet_sdk import ConcurrencyLimitStrategy, Context

from core import GenerationConfig
from core.base import OrchestrationProvider, R2RException
from core.base.abstractions import (
    KGEnrichmentStatus,
    KGExtraction,
    KGExtractionStatus,
)

from ...services import GraphService

logger = logging.getLogger()
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hatchet_sdk import Hatchet


def hatchet_kg_factory(
    orchestration_provider: OrchestrationProvider, service: GraphService
) -> dict[str, "Hatchet.Workflow"]:
    def convert_to_dict(input_data):
        """
        Converts input data back to a plain dictionary format, handling special cases like UUID and GenerationConfig.
        This is the inverse of get_input_data_dict.

        Args:
            input_data: Dictionary containing the input data with potentially special types

        Returns:
            Dictionary with all values converted to basic Python types
        """
        output_data = {}

        for key, value in input_data.items():
            if value is None:
                output_data[key] = None
                continue

            # Convert UUID to string
            if isinstance(value, uuid.UUID):
                output_data[key] = str(value)

            try:
                output_data[key] = value.model_dump()
            except Exception:
                # Handle nested dictionaries that might contain settings
                if isinstance(value, dict):
                    output_data[key] = convert_to_dict(value)

                # Handle lists that might contain dictionaries
                elif isinstance(value, list):
                    output_data[key] = [
                        (
                            convert_to_dict(item)
                            if isinstance(item, dict)
                            else item
                        )
                        for item in value
                    ]

                # All other types can be directly assigned
                else:
                    output_data[key] = value

        return output_data

    def get_input_data_dict(input_data):
        for key, value in input_data.items():
            if value is None:
                continue

            if key == "document_id":
                input_data[key] = uuid.UUID(value)

            if key == "collection_id":
                input_data[key] = uuid.UUID(value)

            if key == "graph_id":
                input_data[key] = uuid.UUID(value)

            if key == "graph_creation_settings":
                with contextlib.suppress(Exception):
                    input_data[key] = json.loads(value)
                input_data[key]["generation_config"] = GenerationConfig(
                    **input_data[key]["generation_config"]
                )
            if key == "graph_enrichment_settings":
                with contextlib.suppress(Exception):
                    input_data[key] = json.loads(value)

            if key == "generation_config":
                input_data[key] = GenerationConfig(**input_data[key])
        return input_data

    @orchestration_provider.workflow(name="extract-triples", timeout="360m")
    class CreateGraphWorkflow:
        @orchestration_provider.concurrency(  # type: ignore
            max_runs=orchestration_provider.config.kg_concurrency_limit,  # type: ignore
            limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
        )
        def concurrency(self, context: Context) -> str:
            # TODO: Possible bug in hatchet, the job can't find context.workflow_input() when rerun
            with contextlib.suppress(Exception):
                return str(
                    context.workflow_input()["request"]["collection_id"]
                )

        def __init__(self, kg_service: GraphService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=1, timeout="360m")
        async def kg_extraction(self, context: Context) -> dict:
            request = context.workflow_input()["request"]

            input_data = get_input_data_dict(request)
            document_id = input_data.get("document_id", None)
            collection_id = input_data.get("collection_id", None)

            await self.kg_service.providers.database.documents_handler.set_workflow_status(
                id=document_id,
                status_type="extraction_status",
                status=KGExtractionStatus.PROCESSING,
            )

            if collection_id and not document_id:
                document_ids = (
                    await self.kg_service.get_document_ids_for_create_graph(
                        collection_id=collection_id,
                        **input_data["graph_creation_settings"],
                    )
                )
                workflows = []

                for document_id in document_ids:
                    input_data_copy = input_data.copy()
                    input_data_copy["collection_id"] = str(
                        input_data_copy["collection_id"]
                    )
                    input_data_copy["document_id"] = str(document_id)

                    workflows.append(
                        context.aio.spawn_workflow(
                            "extract-triples",
                            {
                                "request": {
                                    **convert_to_dict(input_data_copy),
                                }
                            },
                            key=str(document_id),
                        )
                    )
                # Wait for all workflows to complete
                results = await asyncio.gather(*workflows)
                return {
                    "result": f"successfully submitted kg relationships extraction for document {document_id}",
                    "document_id": str(collection_id),
                }

            else:
                # Extract relationships and store them
                extractions = []
                async for extraction in self.kg_service.kg_extraction(
                    document_id=document_id,
                    **input_data["graph_creation_settings"],
                ):
                    logger.info(
                        f"Found extraction with {len(extraction.entities)} entities"
                    )
                    extractions.append(extraction)

                await self.kg_service.store_kg_extractions(extractions)

                logger.info(
                    f"Successfully ran kg relationships extraction for document {document_id}"
                )

                return {
                    "result": f"successfully ran kg relationships extraction for document {document_id}",
                    "document_id": str(document_id),
                }

        @orchestration_provider.step(
            retries=1, timeout="360m", parents=["kg_extraction"]
        )
        async def kg_entity_description(self, context: Context) -> dict:
            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )
            document_id = input_data.get("document_id", None)

            # Describe the entities in the graph
            await self.kg_service.kg_entity_description(
                document_id=document_id,
                **input_data["graph_creation_settings"],
            )

            logger.info(
                f"Successfully ran kg entity description for document {document_id}"
            )

            if (
                service.providers.database.config.graph_creation_settings.automatic_deduplication
            ):
                extract_input = {
                    "document_id": str(document_id),
                }

                extract_result = (
                    await context.aio.spawn_workflow(
                        "deduplicate-document-entities",
                        {"request": extract_input},
                    )
                ).result()

                await asyncio.gather(extract_result)

            return {
                "result": f"successfully ran kg entity description for document {document_id}"
            }

        @orchestration_provider.failure()
        async def on_failure(self, context: Context) -> None:
            request = context.workflow_input().get("request", {})
            document_id = request.get("document_id")

            if not document_id:
                logger.info(
                    "No document id was found in workflow input to mark a failure."
                )
                return

            try:
                await self.kg_service.providers.database.documents_handler.set_workflow_status(
                    id=uuid.UUID(document_id),
                    status_type="extraction_status",
                    status=KGExtractionStatus.FAILED,
                )
                logger.info(
                    f"Updated KG extraction status for {document_id} to FAILED"
                )
            except Exception as e:
                logger.error(
                    f"Failed to update document status for {document_id}: {e}"
                )

    @orchestration_provider.workflow(name="build-communities", timeout="360m")
    class EnrichGraphWorkflow:
        def __init__(self, kg_service: GraphService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=1, timeout="360m", parents=[])
        async def kg_clustering(self, context: Context) -> dict:
            logger.info("Running KG Clustering")
            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )

            # Get the collection_id and graph_id
            collection_id = input_data.get("collection_id", None)
            graph_id = input_data.get("graph_id", None)

            # Check current workflow status
            workflow_status = await self.kg_service.providers.database.documents_handler.get_workflow_status(
                id=collection_id,
                status_type="graph_cluster_status",
            )

            if workflow_status == KGEnrichmentStatus.SUCCESS:
                raise R2RException(
                    "Communities have already been built for this collection. To build communities again, first reset the graph.",
                    400,
                )

            # Run clustering
            try:
                kg_clustering_results = await self.kg_service.kg_clustering(
                    collection_id=collection_id,
                    graph_id=graph_id,
                    **input_data["graph_enrichment_settings"],
                )

                num_communities = kg_clustering_results["num_communities"][0]

                if num_communities == 0:
                    raise R2RException("No communities found", 400)

                logger.info(
                    f"Successfully ran kg clustering: {json.dumps(kg_clustering_results)}"
                )

                return {
                    "result": kg_clustering_results,
                }
            except Exception as e:
                await self.kg_service.providers.database.documents_handler.set_workflow_status(
                    id=collection_id,
                    status_type="graph_cluster_status",
                    status=KGEnrichmentStatus.FAILED,
                )
                raise e

        @orchestration_provider.step(
            retries=1, timeout="360m", parents=["kg_clustering"]
        )
        async def kg_community_summary(self, context: Context) -> dict:
            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )
            collection_id = input_data.get("collection_id", None)
            graph_id = input_data.get("graph_id", None)
            # Get number of communities from previous step
            num_communities = context.step_output("kg_clustering")["result"][
                "num_communities"
            ][0]

            # Calculate batching
            parallel_communities = min(100, num_communities)
            total_workflows = math.ceil(num_communities / parallel_communities)
            workflows = []

            logger.info(
                f"Running KG Community Summary for {num_communities} communities, spawning {total_workflows} workflows"
            )

            # Spawn summary workflows
            for i in range(total_workflows):
                offset = i * parallel_communities
                limit = min(parallel_communities, num_communities - offset)

                workflows.append(
                    (
                        await context.aio.spawn_workflow(
                            "kg-community-summary",
                            {
                                "request": {
                                    "offset": offset,
                                    "limit": limit,
                                    "graph_id": (
                                        str(graph_id) if graph_id else None
                                    ),
                                    "collection_id": (
                                        str(collection_id)
                                        if collection_id
                                        else None
                                    ),
                                    **input_data["graph_enrichment_settings"],
                                }
                            },
                            key=f"{i}/{total_workflows}_community_summary",
                        )
                    ).result()
                )

            results = await asyncio.gather(*workflows)
            logger.info(
                f"Completed {len(results)} community summary workflows"
            )

            # Update statuses
            document_ids = await self.kg_service.providers.database.documents_handler.get_document_ids_by_status(
                status_type="extraction_status",
                status=KGExtractionStatus.SUCCESS,
                collection_id=collection_id,
            )

            await self.kg_service.providers.database.documents_handler.set_workflow_status(
                id=document_ids,
                status_type="extraction_status",
                status=KGExtractionStatus.ENRICHED,
            )

            await self.kg_service.providers.database.documents_handler.set_workflow_status(
                id=collection_id,
                status_type="graph_cluster_status",
                status=KGEnrichmentStatus.SUCCESS,
            )

            return {
                "result": f"Successfully completed enrichment with {len(results)} summary workflows"
            }

        @orchestration_provider.failure()
        async def on_failure(self, context: Context) -> None:
            collection_id = context.workflow_input()["request"].get(
                "collection_id", None
            )
            if collection_id:
                await self.kg_service.providers.database.documents_handler.set_workflow_status(
                    id=uuid.UUID(collection_id),
                    status_type="graph_cluster_status",
                    status=KGEnrichmentStatus.FAILED,
                )

    @orchestration_provider.workflow(
        name="kg-community-summary", timeout="360m"
    )
    class KGCommunitySummaryWorkflow:
        def __init__(self, kg_service: GraphService):
            self.kg_service = kg_service

        @orchestration_provider.concurrency(  # type: ignore
            max_runs=orchestration_provider.config.kg_concurrency_limit,  # type: ignore
            limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
        )
        def concurrency(self, context: Context) -> str:
            # TODO: Possible bug in hatchet, the job can't find context.workflow_input() when rerun
            try:
                return str(
                    context.workflow_input()["request"]["collection_id"]
                )
            except Exception as e:
                return str(uuid.uuid4())

        @orchestration_provider.step(retries=1, timeout="360m")
        async def kg_community_summary(self, context: Context) -> dict:
            start_time = time.time()

            logger.info

            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )

            community_summary = await self.kg_service.kg_community_summary(
                **input_data,
            )
            logger.info(
                f"Successfully ran kg community summary for communities {input_data['offset']} to {input_data['offset'] + len(community_summary)} in {time.time() - start_time:.2f} seconds "
            )
            return {
                "result": f"successfully ran kg community summary for communities {input_data['offset']} to {input_data['offset'] + len(community_summary)}"
            }

    @orchestration_provider.workflow(
        name="deduplicate-document-entities", timeout="360m"
    )
    class DeduplicateDocumentEntitiesWorkflow:
        def __init__(self, kg_service: GraphService):
            self.kg_service = kg_service

        @orchestration_provider.concurrency(  # type: ignore
            max_runs=orchestration_provider.config.kg_concurrency_limit,  # type: ignore
            limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
        )
        def concurrency(self, context: Context) -> str:
            # TODO: Possible bug in hatchet, the job can't find context.workflow_input() when rerun
            try:
                return str(context.workflow_input()["request"]["document_id"])
            except Exception as e:
                return str(uuid.uuid4())

        @orchestration_provider.step(retries=1, timeout="360m")
        async def deduplicate_document_entities(
            self, context: Context
        ) -> dict:
            start_time = time.time()

            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )

            document_id = input_data.get("document_id", None)

            await service.deduplicate_document_entities(
                document_id=document_id,
            )
            logger.info(
                f"Successfully ran deduplication for document {document_id} in {time.time() - start_time:.2f} seconds "
            )
            return {
                "result": f"Successfully ran deduplication for document {document_id}"
            }

    return {
        "extract-triples": CreateGraphWorkflow(service),
        "build-communities": EnrichGraphWorkflow(service),
        "kg-community-summary": KGCommunitySummaryWorkflow(service),
        "deduplicate-document-entities": DeduplicateDocumentEntitiesWorkflow(
            service
        ),
    }
