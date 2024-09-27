import asyncio
import json
import logging
import uuid
import math

from hatchet_sdk import ConcurrencyLimitStrategy, Context

from core import GenerationConfig, IngestionStatus, KGCreationSettings
from core.base import R2RDocumentProcessingError
from core.base.abstractions import KGCreationStatus, KGEnrichmentStatus
from core.base import KGCreationSettings, KGEnrichmentSettings

from ..services import KgService
from .base import r2r_hatchet

logger = logging.getLogger(__name__)


@r2r_hatchet.workflow(name="kg-ede", timeout="360m")
class KgExtractDescribeEmbedWorkflow:
    def __init__(self, kg_service: KgService):
        self.kg_service = kg_service

    @r2r_hatchet.step(name="kg_extract", parents=[], retries=3, timeout="360m")
    async def kg_extract(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]
        document_id = uuid.UUID(input_data["document_id"])
        fragment_merge_count = input_data["fragment_merge_count"]
        max_knowledge_triples = input_data["max_knowledge_triples"]
        entity_types = input_data["entity_types"]
        relation_types = input_data["relation_types"]

        await self.kg_service.providers.database.relational.set_workflow_status(
            id=document_id,
            status_type="kg_creation",
            status=KGCreationStatus.PROCESSING,
        )

        errors = await self.kg_service.kg_extract_and_store(
            document_id=document_id,
            generation_config=GenerationConfig(
                **input_data["generation_config"]
            ),
            fragment_merge_count=fragment_merge_count,
            max_knowledge_triples=max_knowledge_triples,
            entity_types=entity_types,
            relation_types=relation_types,
        )

        if len(errors) == 0:
            await self.kg_service.providers.database.relational.set_workflow_status(
                id=document_id,
                status_type="kg_creation",
                status=KGCreationStatus.SUCCESS,
            )
        else:
            raise ValueError(
                f"Error in kg_extract_and_store: No Triples Extracted"
            )
    
    @r2r_hatchet.step(retries=3, timeout="360m")
    async def kg_node_description(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]
        max_description_input_length = input_data[
            "max_description_input_length"
        ]

        entity_count = await self.kg_service.providers.kg.get_entity_count(
            project_name=input_data["project_name"],
            document_id=input_data["document_id"],
        )

        # process 50 entities at a time
        num_batches = math.ceil(entity_count / 50)  
        workflows = []


        for i in range(num_batches):
            logger.info(f"Running kg_node_description for batch {i+1}/{num_batches} for document {input_data['document_id']}")
            await self.kg_service.kg_node_description(
                offset=i * 50,
                limit=50,
                document_id=input_data["document_id"],
                max_description_input_length=max_description_input_length,
                project_name=input_data["project_name"],
            )
        return {"result": None}

    # on failure step hatchet
    @r2r_hatchet.on_failure_step()
    async def on_failure(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]
        document_id = uuid.UUID(input_data["document_id"])
        await self.kg_service.providers.database.relational.set_workflow_status(
            id=document_id,
            status_type="kg_creation",
            status=KGCreationStatus.FAILURE,
        )

@r2r_hatchet.workflow(name="create-graph", timeout="360m")
class CreateGraphWorkflow:
    def __init__(self, kg_service: KgService):
        self.kg_service = kg_service

    @r2r_hatchet.step(retries=1)
    async def kg_extraction_ingress(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]

        kg_creation_settings = KGCreationSettings(
            **json.loads(input_data["kg_creation_settings"])
        )

        doucment_ids = input_data["document_ids"]

        if not doucment_ids:
            document_status_filter = [
                KGCreationStatus.PENDING,
                KGCreationStatus.FAILURE,
            ]
            if kg_creation_settings.force_kg_creation:
                document_status_filter += [
                    KGCreationStatus.SUCCESS,
                    KGCreationStatus.PROCESSING,
                ]

            document_ids = await self.kg_service.providers.database.relational.get_document_ids_by_status(
                status_type="kg_creation", status=document_status_filter
            )

        results = []
        for cnt, document_id in enumerate(document_ids):
            logger.info(
                f"Running Graph Creation Workflow for document ID: {document_id}"
            )
            results.append(
                (
                    context.aio.spawn_workflow(
                        "kg-ede",
                        {
                            "request": {
                                "document_id": str(document_id),
                                "fragment_merge_count": kg_creation_settings.fragment_merge_count,
                                "max_knowledge_triples": kg_creation_settings.max_knowledge_triples,
                                "generation_config": kg_creation_settings.generation_config.to_dict(),
                                "entity_types": kg_creation_settings.entity_types,
                                "relation_types": kg_creation_settings.relation_types,
                            }
                        },
                        key=f"kg-csd-{cnt}/{len(document_ids)}",
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


@r2r_hatchet.workflow(name="enrich-graph", timeout="60m")
class EnrichGraphWorkflow:
    def __init__(self, kg_service: KgService):
        self.kg_service = kg_service

    @r2r_hatchet.step(retries=3, parents=[], timeout="60m")
    async def kg_clustering(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]

        project_name = input_data["project_name"]
        collection_id = input_data["collection_id"]

        kg_enrichment_settings = KGEnrichmentSettings(
            **json.loads(input_data["kg_enrichment_settings"])
        )

        collection_status = await self.kg_service.providers.database.relational.get_workflow_status(
            id=collection_id, status_type="kg_enrichment"
        )

        if collection_status in [
            KGEnrichmentStatus.PENDING,
            KGEnrichmentStatus.PROCESSING,
        ]:
            log_msg = f"Collection {collection_id} is still being enriched, skipping clustering"
            logger.info(log_msg)
            return {"result": log_msg}

        else:
            await self.kg_service.providers.database.relational.set_workflow_status(
                id=collection_id,
                status_type="kg_enrichment",
                status=KGEnrichmentStatus.PROCESSING,
            )

        try:
            if not kg_enrichment_settings.skip_clustering:
                results = await self.kg_service.kg_clustering(
                    project_name,
                    collection_id,
                    kg_enrichment_settings.leiden_params,
                    kg_enrichment_settings.generation_config,
                )

                result = results[0]
                num_communities = result["num_communities"]
                parallel_communities = min(100, num_communities)
                total_workflows = math.ceil(
                    num_communities / parallel_communities
                )
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
                                    "generation_config": kg_enrichment_settings.generation_config.to_dict(),
                                    "max_summary_input_length": kg_enrichment_settings.max_summary_input_length,
                                    "project_name": project_name,
                                    "collection_id": collection_id,
                                }
                            },
                            key=f"{i}/{total_workflows}_community_summary",
                        )
                    )
                results = await asyncio.gather(*workflows)
                return {
                    "result": f"Finished {total_workflows} community summary workflows"
                }
            else:
                logger.info(
                    "Skipping Leiden clustering as skip_clustering is True, also skipping community summary workflows"
                )
                return {"result": "skipped"}

        except Exception as e:
            logger.error(f"Error in kg_clustering: {str(e)}", exc_info=True)
            # documents_overview = (
            #     await self.kg_service.providers.database.relational.get_documents_overview()
            # )
            # documents_overview = documents_overview["results"]
            # for document_overview in documents_overview:
            #     if (
            #         document_overview.restructuring_status
            #         == .ENRICHING
            #     ):
            #         document_overview.restructuring_status = (
            #             .ENRICHMENT_FAILURE
            #         )
            #         await self.kg_service.providers.database.relational.upsert_documents_overview(
            #             document_overview
            #         )
            #         logger.error(
            #             f"Error in kg_clustering for document {document_overview.id}: {str(e)}"
            #         )
            # raise e

        finally:

            pass

            # documents_overview = (
            #     await self.kg_service.providers.database.relational.get_documents_overview()
            # )
            # documents_overview = documents_overview["results"]
            # for document_overview in documents_overview:
            #     if (
            #         document_overview.restructuring_status
            #         == RestructureStatus.ENRICHING
            #     ):
            #         document_overview.restructuring_status = (
            #             RestructureStatus.ENRICHED
            #         )

            # await self.kg_service.providers.database.relational.upsert_documents_overview(
            #     documents_overview
            # )
            # return {"result": None}


@r2r_hatchet.workflow(name="kg-community-summary", timeout="60m")
class KGCommunitySummaryWorkflow:
    def __init__(self, kg_service: KgService):
        self.kg_service = kg_service

    @r2r_hatchet.step(retries=1, timeout="60m")
    async def kg_community_summary(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]
        offset = input_data["offset"]
        limit = input_data["limit"]
        generation_config = GenerationConfig(**input_data["generation_config"])
        max_summary_input_length = input_data["max_summary_input_length"]
        project_name = input_data["project_name"]
        collection_id = input_data["collection_id"]

        await self.kg_service.kg_community_summary(
            offset=offset,
            limit=limit,
            max_summary_input_length=max_summary_input_length,
            generation_config=generation_config,
            project_name=project_name,
            collection_id=collection_id,
        )
        return {"result": None}
