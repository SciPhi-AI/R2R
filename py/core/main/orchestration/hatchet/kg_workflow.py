import asyncio
import json
import logging
import math
import time
import uuid

from hatchet_sdk import ConcurrencyLimitStrategy, Context

from core import GenerationConfig
from core.base import OrchestrationProvider, R2RException
from core.base.abstractions import KGEnrichmentStatus, KGExtractionStatus

from ...services import KgService

logger = logging.getLogger()
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hatchet_sdk import Hatchet


def hatchet_kg_factory(
    orchestration_provider: OrchestrationProvider, service: KgService
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
            except:
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
                try:
                    input_data[key] = json.loads(value)
                except:
                    pass
                input_data[key]["generation_config"] = GenerationConfig(
                    **input_data[key]["generation_config"]
                )
            if key == "graph_enrichment_settings":
                try:
                    input_data[key] = json.loads(value)
                except:
                    pass

            if key == "graph_entity_deduplication_settings":
                try:
                    input_data[key] = json.loads(value)
                except:
                    pass

                if isinstance(input_data[key]["generation_config"], str):
                    input_data[key]["generation_config"] = json.loads(
                        input_data[key]["generation_config"]
                    )

                input_data[key]["generation_config"] = GenerationConfig(
                    **input_data[key]["generation_config"]
                )

                logger.info(
                    f"KG Entity Deduplication Settings: {input_data[key]}"
                )

            if key == "generation_config":
                input_data[key] = GenerationConfig(**input_data[key])
        return input_data

    @orchestration_provider.workflow(name="kg-extract", timeout="360m")
    class KGExtractDescribeEmbedWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.concurrency(  # type: ignore
            max_runs=orchestration_provider.config.kg_creation_concurrency_limit,  # type: ignore
            limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
        )
        def concurrency(self, context: Context) -> str:
            # TODO: Possible bug in hatchet, the job can't find context.workflow_input() when rerun
            try:
                return str(context.workflow_input()["request"]["graph_id"])
            except Exception as e:
                return str(uuid.uuid4())

        @orchestration_provider.step(retries=1, timeout="360m")
        async def kg_extract(self, context: Context) -> dict:
            logger.info("Initiating kg workflow, step: kg_extract")

            start_time = time.time()

            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )

            # context.log(f"Running KG Extraction for collection ID: {input_data['graph_id']}")
            document_id = input_data.get("document_id", None)
            collection_id = input_data.get("collection_id", None)
            if collection_id and document_id:
                raise R2RException(
                    "Both collection_id and document_id were provided. Please provide only one.",
                    400,
                )
            elif collection_id:
                document_ids = (
                    await self.kg_service.get_document_ids_for_create_graph(
                        collection_id=collection_id,
                        **input_data["graph_creation_settings"],
                    )
                )
                workflows = []

                for document_id in document_ids:
                    input_data_copy = input_data.copy()
                    input_data_copy["document_id"] = document_id
                    input_data_copy.pop("collection_id", None)

                    workflows.append(
                        context.aio.spawn_workflow(
                            "kg-extract",
                            {
                                "request": {
                                    **input_data_copy,
                                }
                            },
                            key=str(document_id),
                        )
                    )
                # Wait for all workflows to complete
                results = await asyncio.gather(*workflows)
                return {
                    "result": f"successfully submitted extraction request {document_id} in {time.time() - start_time:.2f} seconds",
                }

            # await self.kg_service.kg_relationships_extraction(
            #     document_id=document_id,
            #     **input_data["graph_creation_settings"],
            # )
            else:
                extractions = []
                async for extraction in service.kg_extraction(
                    document_id=document_id,
                    **input_data["graph_creation_settings"],
                ):
                    print(
                        "found extraction w/ entities = = ",
                        len(extraction.entities),
                    )
                    extractions.append(extraction)
                await service.store_kg_extractions(extractions)

                logger.info(
                    f"Successfully ran kg relationships extraction for document {document_id}"
                )

            return {
                "result": f"successfully ran kg relationships extraction for document {document_id} in {time.time() - start_time:.2f} seconds",
            }

        @orchestration_provider.step(
            retries=1, timeout="360m", parents=["kg_extract"]
        )
        async def kg_entity_description(self, context: Context) -> dict:

            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )
            document_id = input_data.get("document_id", None)

            await self.kg_service.kg_entity_description(
                document_id=document_id,
                **input_data["graph_creation_settings"],
            )

            logger.info(
                f"Successfully ran kg node description for document {document_id}"
            )

            return {
                "result": f"successfully ran kg node description for document {document_id}"
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
                await self.kg_service.providers.database.set_workflow_status(
                    id=uuid.UUID(document_id),
                    status_type="extraction_status",
                    status=KGExtractionStatus.FAILED,
                )
                context.log(
                    f"Updated KG extraction status for {document_id} to FAILED"
                )

            except Exception as e:
                context.log(
                    f"Failed to update document status for {document_id}: {e}"
                )

    @orchestration_provider.workflow(name="extract-triples", timeout="600m")
    class CreateGraphWorkflow:

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
                pass

        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=1)
        async def kg_extraction(self, context: Context) -> dict:
            request = context.workflow_input()["request"]
            print('context.workflow_input()["request"] = ', request)

            input_data = get_input_data_dict(request)
            document_id = input_data.get("document_id", None)
            collection_id = input_data.get("collection_id", None)

            if collection_id and not document_id:
                document_ids = (
                    await self.kg_service.get_document_ids_for_create_graph(
                        collection_id=collection_id,
                        **input_data["graph_creation_settings"],
                    )
                )
                workflows = []

                for document_id in document_ids:
                    print("extracting = ", document_id)
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

        @orchestration_provider.step(retries=1, parents=["kg_extraction"])
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
                await self.kg_service.providers.database.set_workflow_status(
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

    # class CreateGraphWorkflow:
    #     def __init__(self, kg_service: KgService):
    #         self.kg_service = kg_service

    #     @orchestration_provider.step(retries=1)
    #     async def get_document_ids_for_create_graph(
    #         self, context: Context
    #     ) -> dict:

    #         input_data = get_input_data_dict(
    #             context.workflow_input()["request"]
    #         )

    #         if "collection_id" in input_data:

    #             collection_id = input_data["collection_id"]

    #             return_val = {
    #                 "document_ids": [
    #                     str(doc_id)
    #                     for doc_id in await self.kg_service.get_document_ids_for_create_graph(
    #                         collection_id=collection_id,
    #                         **input_data["graph_creation_settings"],
    #                     )
    #                 ]
    #             }

    #             if len(return_val["document_ids"]) == 0:
    #                 raise ValueError(
    #                     "No documents to process, either all documents to create the graph were already created or in progress, or the collection is empty."
    #                 )
    #         else:
    #             return_val = {"document_ids": [str(input_data["document_id"])]}

    #         return return_val

    #     @orchestration_provider.step(
    #         retries=1, parents=["get_document_ids_for_create_graph"]
    #     )
    #     async def kg_extraction_ingress(self, context: Context) -> dict:

    #         document_ids = [
    #             uuid.UUID(doc_id)
    #             for doc_id in context.step_output(
    #                 "get_document_ids_for_create_graph"
    #             )["document_ids"]
    #         ]
    #         results = []
    #         for cnt, document_id in enumerate(document_ids):
    #             logger.info(
    #                 f"Running Graph Creation Workflow for document ID: {document_id}"
    #             )
    #             results.append(
    #                 (
    #                     await context.aio.spawn_workflow(
    #                         "kg-extract",
    #                         {
    #                             "request": {
    #                                 "document_id": str(document_id),
    #                                 "graph_creation_settings": context.workflow_input()[
    #                                     "request"
    #                                 ][
    #                                     "graph_creation_settings"
    #                                 ],
    #                             }
    #                         },
    #                         key=f"kg-extract-{cnt}/{len(document_ids)}",
    #                     )
    #                 ).result()
    #             )

    #         if not document_ids:
    #             logger.info(
    #                 "No documents to process, either all graphs were created or in progress, or no documents were provided. Skipping graph creation."
    #             )
    #             return {"result": "No documents to process"}

    #         logger.info(f"Ran {len(results)} workflows for graph creation")
    #         results = await asyncio.gather(*results)
    #         return {
    #             "result": f"successfully ran graph creation workflows for {len(results)} documents"
    #         }

    #     @orchestration_provider.step(
    #         retries=1, parents=["kg_extraction_ingress"]
    #     )
    #     async def update_enrichment_status(self, context: Context) -> dict:

    #         enrichment_status = (
    #             await self.kg_service.providers.database.get_workflow_status(
    #                 id=uuid.UUID(
    #                     context.workflow_input()["request"]["collection_id"]
    #                 ),
    #                 status_type="graph_cluster_status",
    #             )
    #         )

    #         if enrichment_status == KGEnrichmentStatus.SUCCESS:
    #             await self.kg_service.providers.database.set_workflow_status(
    #                 id=uuid.UUID(
    #                     context.workflow_input()["request"]["collection_id"]
    #                 ),
    #                 status_type="graph_cluster_status",
    #                 status=KGEnrichmentStatus.OUTDATED,
    #             )

    #             logger.info(
    #                 f"Updated enrichment status for collection {context.workflow_input()['request']['collection_id']} to OUTDATED because an older enrichment was already successful"
    #             )

    #         return {
    #             "result": f"updated enrichment status for collection {context.workflow_input()['request']['collection_id']} to OUTDATED because an older enrichment was already successful"
    #         }

    @orchestration_provider.workflow(
        name="entity-deduplication", timeout="360m"
    )
    class EntityDeduplicationWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=0, timeout="360m")
        async def kg_entity_deduplication_setup(
            self, context: Context
        ) -> dict:

            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )

            graph_id = input_data["graph_id"]

            logger.info(
                f"Running KG Entity Deduplication for collection {graph_id}"
            )
            logger.info(f"Input data: {input_data}")
            logger.info(
                f"KG Entity Deduplication Settings: {input_data['graph_entity_deduplication_settings']}"
            )

            number_of_distinct_entities = (
                await self.kg_service.kg_entity_deduplication(
                    graph_id=graph_id,
                    **input_data["graph_entity_deduplication_settings"],
                )
            )[0]["num_entities"]

            input_data["graph_entity_deduplication_settings"][
                "generation_config"
            ] = input_data["graph_entity_deduplication_settings"][
                "generation_config"
            ].model_dump_json()

            # run 100 entities in one workflow
            total_workflows = math.ceil(number_of_distinct_entities / 100)
            workflows = []
            for i in range(total_workflows):
                offset = i * 100
                workflows.append(
                    context.aio.spawn_workflow(
                        "kg-entity-deduplication-summary",
                        {
                            "request": {
                                "graph_id": graph_id,
                                "offset": offset,
                                "limit": 100,
                                "graph_entity_deduplication_settings": json.dumps(
                                    input_data[
                                        "graph_entity_deduplication_settings"
                                    ]
                                ),
                            }
                        },
                        key=f"{i}/{total_workflows}_entity_deduplication_part",
                    )
                )

            await asyncio.gather(*workflows)
            return {
                "result": f"successfully queued kg entity deduplication for collection {graph_id} with {number_of_distinct_entities} distinct entities"
            }

    @orchestration_provider.workflow(
        name="kg-entity-deduplication-summary", timeout="360m"
    )
    class EntityDeduplicationSummaryWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=0, timeout="360m")
        async def kg_entity_deduplication_summary(
            self, context: Context
        ) -> dict:

            logger.info(
                f"Running KG Entity Deduplication Summary for input data: {context.workflow_input()['request']}"
            )

            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )
            graph_id = input_data["graph_id"]

            await self.kg_service.kg_entity_deduplication_summary(
                graph_id=graph_id,
                offset=input_data["offset"],
                limit=input_data["limit"],
                **input_data["graph_entity_deduplication_settings"],
            )

            return {
                "result": f"successfully queued kg entity deduplication summary for collection {graph_id}"
            }

    @orchestration_provider.workflow(name="build-communities", timeout="360m")
    class EnrichGraphWorkflow:
        def __init__(self, kg_service: KgService):
            self.kg_service = kg_service

        @orchestration_provider.step(retries=1, parents=[], timeout="360m")
        async def kg_clustering(self, context: Context) -> dict:
            logger.info("Running KG Clustering")
            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )

            # Get the collection_id and graph_id
            collection_id = input_data.get("collection_id", None)
            graph_id = input_data.get("graph_id", None)

            # Check current workflow status
            workflow_status = (
                await self.kg_service.providers.database.get_workflow_status(
                    id=collection_id,
                    status_type="graph_cluster_status",
                )
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

                num_communities = kg_clustering_results[0]["num_communities"]

                if num_communities == 0:
                    raise R2RException("No communities found", 400)

                logger.info(
                    f"Successfully ran kg clustering: {json.dumps(kg_clustering_results)}"
                )

                return {
                    "result": f"successfully ran kg clustering",
                    "kg_clustering": kg_clustering_results,
                }
            except Exception as e:
                await self.kg_service.providers.database.set_workflow_status(
                    id=collection_id,
                    status_type="graph_cluster_status",
                    status=KGEnrichmentStatus.FAILED,
                )
                raise e

        @orchestration_provider.step(retries=1, parents=["kg_clustering"])
        async def kg_community_summary(self, context: Context) -> dict:
            input_data = get_input_data_dict(
                context.workflow_input()["request"]
            )
            collection_id = input_data.get("collection_id", None)
            graph_id = input_data.get("graph_id", None)

            # Get number of communities from previous step
            num_communities = context.step_output("kg_clustering")[
                "kg_clustering"
            ][0]["num_communities"]

            # Calculate batching
            parallel_communities = min(100, num_communities[0])
            total_workflows = math.ceil(
                num_communities[0] / parallel_communities
            )
            workflows = []

            logger.info(
                f"Running KG Community Summary for {num_communities} communities, spawning {total_workflows} workflows"
            )

            # Spawn summary workflows
            for i in range(total_workflows):
                offset = i * parallel_communities
                limit = min(parallel_communities, num_communities[0] - offset)

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
            document_ids = await self.kg_service.providers.database.get_document_ids_by_status(
                status_type="extraction_status",
                status=KGExtractionStatus.SUCCESS,
                collection_id=collection_id,
            )

            await self.kg_service.providers.database.set_workflow_status(
                id=document_ids,
                status_type="extraction_status",
                status=KGExtractionStatus.ENRICHED,
            )

            await self.kg_service.providers.database.set_workflow_status(
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
                await self.kg_service.providers.database.set_workflow_status(
                    id=uuid.UUID(collection_id),
                    status_type="graph_cluster_status",
                    status=KGEnrichmentStatus.FAILED,
                )

        # @orchestration_provider.step(retries=1, parents=["kg_clustering"])
        # async def kg_community_summary(self, context: Context) -> dict:

        #     input_data = get_input_data_dict(
        #         context.workflow_input()["request"]
        #     )
        #     graph_id = input_data.get("graph_id", None)
        #     collection_id = input_data.get("collection_id", None)
        #     num_communities = context.step_output("kg_clustering")[
        #         "kg_clustering"
        #     ][0]["num_communities"]
        #     parallel_communities = min(100, num_communities)
        #     total_workflows = math.ceil(num_communities / parallel_communities)
        #     workflows = []

        #     logger.info(
        #         f"Running KG Community Summary for {num_communities} communities, spawning {total_workflows} workflows"
        #     )

        #     for i in range(total_workflows):
        #         offset = i * parallel_communities
        #         workflows.append(
        #             (
        #                 await context.aio.spawn_workflow(
        #                     "kg-community-summary",
        #                     {
        #                         "request": {
        #                             "offset": offset,
        #                             "limit": min(
        #                                 parallel_communities,
        #                                 num_communities - offset,
        #                             ),
        #                             "graph_id": (
        #                                 str(graph_id) if graph_id else None
        #                             ),
        #                             "collection_id": (
        #                                 str(collection_id)
        #                                 if collection_id
        #                                 else None
        #                             ),
        #                             **input_data["graph_enrichment_settings"],
        #                         }
        #                     },
        #                     key=f"{i}/{total_workflows}_community_summary",
        #                 )
        #             ).result()
        #         )

        #     results = await asyncio.gather(*workflows)

        #     logger.info(f"Ran {len(results)} workflows for community summary")

        #     # set status to success
        #     # for all documents in the collection, set kg_creation_status to ENRICHED
        #     document_ids = await self.kg_service.providers.database.get_document_ids_by_status(
        #         status_type="extraction_status",
        #         status=KGExtractionStatus.SUCCESS,
        #         collection_id=collection_id,
        #     )

        #     await self.kg_service.providers.database.set_workflow_status(
        #         id=document_ids,
        #         status_type="extraction_status",
        #         status=KGExtractionStatus.ENRICHED,
        #     )

        #     await self.kg_service.providers.database.set_workflow_status(
        #         id=graph_id,
        #         status_type="graph_cluster_status",
        #         status=KGEnrichmentStatus.SUCCESS,
        #     )

        #     return {
        #         "result": f"Successfully completed enrichment for collection {graph_id} in {len(results)} workflows."
        #     }

        # @orchestration_provider.failure()
        # async def on_failure(self, context: Context) -> None:
        #     collection_id = context.workflow_input()["request"].get(
        #         "collection_id", None
        #     )
        #     await self.kg_service.providers.database.set_workflow_status(
        #         id=uuid.UUID(collection_id),
        #         status_type="graph_cluster_status",
        #         status=KGEnrichmentStatus.FAILED,
        #     )

    @orchestration_provider.workflow(
        name="kg-community-summary", timeout="360m"
    )
    class KGCommunitySummaryWorkflow:
        def __init__(self, kg_service: KgService):
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

    return {
        "kg-extract": KGExtractDescribeEmbedWorkflow(service),
        "extract-triples": CreateGraphWorkflow(service),
        "build-communities": EnrichGraphWorkflow(service),
        "kg-community-summary": KGCommunitySummaryWorkflow(service),
        "kg-entity-deduplication": EntityDeduplicationWorkflow(service),
        "kg-entity-deduplication-summary": EntityDeduplicationSummaryWorkflow(
            service
        ),
    }
