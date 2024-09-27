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

from ..services import KGService
from .base import r2r_hatchet

logger = logging.getLogger(__name__)


@r2r_hatchet.workflow(name="kg-esd", timeout="60m")
class KgExtractStoreDescribeWorkflow:
    def __init__(self, kg_service: KGService):
        self.kg_service = kg_service

    @r2r_hatchet.step(retries=3, timeout="60m")
    async def kg_extract_and_store(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]
        document_id = uuid.UUID(input_data["document_id"])
        fragment_merge_count = input_data["fragment_merge_count"]
        max_knowledge_triples = input_data["max_knowledge_triples"]
        entity_types = input_data["entity_types"]
        relation_types = input_data["relation_types"]

        try:

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

        except Exception as e:

            await self.kg_service.providers.database.relational.set_workflow_status(
                id=document_id,
                status_type="kg_creation",
                status=KGCreationStatus.FAILURE,
            )

            raise R2RDocumentProcessingError(
                error_message=e,
                document_id=document_id,
            ) from e

        return {"result": None}

    # TODO: parallelize embedding and storing


@r2r_hatchet.workflow(name="create-graph", timeout="60m")
class CreateGraphWorkflow:
    def __init__(self, kg_service: KGService):
        self.kg_service = kg_service

    @r2r_hatchet.step(retries=1)
    async def kg_extraction_ingress(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]

        kg_creation_settings = KGCreationSettings(
            **json.loads(input_data["kg_creation_settings"])
        )

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
                        "kg-esd",
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
    def __init__(self, kg_service: KGService):
        self.kg_service = kg_service

    @r2r_hatchet.step(retries=3, parents=[], timeout="60m")
    async def kg_clustering(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]

        project_name = input_data["project_name"]
        collection_id = input_data["collection_id"]

        kg_enrichment_settings = KGEnrichmentSettings(
            **json.loads(input_data["kg_enrichment_settings"])
        )

        # skip_clustering = input_data["skip_clustering"]
        # force_enrichment = input_data["force_enrichment"]
        # leiden_params = input_data["leiden_params"]
        # max_summary_input_length = input_data["max_summary_input_length"]
        # project_name = input_data["project_name"]
        # generation_config = GenerationConfig(**input_data["generation_config"])

        # todo: check if documets are already being clustered
        # check if any documents are still being restructured, need to explicitly set the force_clustering flag to true to run clustering if documents are still being restructured

        collection_status = await self.kg_service.providers.database.relational.get_workflow_status(
            id=collection_id, status_type="kg_enrichment"
        )

        if collection_status in [
            KGEnrichmentStatus.PENDING,
            KGEnrichmentStatus.PROCESSING,
        ]:
            logger.info(
                f"Collection {collection_id} is still being enriched, skipping clustering"
            )
            return {"result": "skipped"}

        else:
            await self.kg_service.providers.database.relational.set_workflow_status(
                id=collection_id,
                status_type="kg_enrichment",
                status=KGEnrichmentStatus.PROCESSING,
            )

        try:
            if not skip_clustering:
                results = await self.kg_service.kg_clustering(
                    leiden_params, generation_config, project_name
                )

                result = results[0]
                num_communities = result["num_communities"]
                parallel_communities = min(10, num_communities)
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
                                    "generation_config": generation_config.to_dict(),
                                    "max_summary_input_length": max_summary_input_length,
                                    "project_name": project_name,
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
            documents_overview = (
                await self.kg_service.providers.database.relational.get_documents_overview()
            )
            documents_overview = documents_overview["results"]
            for document_overview in documents_overview:
                if (
                    document_overview.restructuring_status
                    == RestructureStatus.ENRICHING
                ):
                    document_overview.restructuring_status = (
                        RestructureStatus.ENRICHMENT_FAILURE
                    )
                    await self.kg_service.providers.database.relational.upsert_documents_overview(
                        document_overview
                    )
                    logger.error(
                        f"Error in kg_clustering for document {document_overview.id}: {str(e)}"
                    )
            raise e

        finally:

            documents_overview = (
                await self.kg_service.providers.database.relational.get_documents_overview()
            )
            documents_overview = documents_overview["results"]
            for document_overview in documents_overview:
                if (
                    document_overview.restructuring_status
                    == RestructureStatus.ENRICHING
                ):
                    document_overview.restructuring_status = (
                        RestructureStatus.ENRICHED
                    )

            await self.kg_service.providers.database.relational.upsert_documents_overview(
                documents_overview
            )
            return {"result": None}


@r2r_hatchet.workflow(name="kg-community-summary", timeout="60m")
class KGCommunitySummaryWorkflow:
    def __init__(self, kg_service: KGService):
        self.kg_service = kg_service

    @r2r_hatchet.step(retries=1, timeout="60m")
    async def kg_community_summary(self, context: Context) -> dict:
        input_data = context.workflow_input()["request"]
        offset = input_data["offset"]
        limit = input_data["limit"]
        generation_config = GenerationConfig(**input_data["generation_config"])
        max_summary_input_length = input_data["max_summary_input_length"]
        project_name = input_data["project_name"]

        await self.kg_service.kg_community_summary(
            offset=offset,
            limit=limit,
            max_summary_input_length=max_summary_input_length,
            generation_config=generation_config,
            project_name=project_name,
        )
        return {"result": None}
