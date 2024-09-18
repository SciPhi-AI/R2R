import asyncio
import json
import logging
import uuid

from hatchet_sdk import Context

from core import GenerationConfig, IngestionStatus, KGCreationSettings
from core.base import R2RDocumentProcessingError
from core.base.abstractions.document import RestructureStatus

from ..services import RestructureService
from .base import r2r_hatchet

logger = logging.getLogger(__name__)


@r2r_hatchet.workflow(name="kg-extract-and-store", timeout="60m")
class KgExtractAndStoreWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=3, timeout="60m")
    async def kg_extract_and_store(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]
        document_id = uuid.UUID(input_data["document_id"])
        fragment_merge_count = input_data["fragment_merge_count"]
        max_knowledge_triples = input_data["max_knowledge_triples"]
        entity_types = input_data["entity_types"]
        relation_types = input_data["relation_types"]

        document_overview = (
            await self.restructure_service.providers.database.relational.get_documents_overview(
                filter_document_ids=[document_id]
            )
        )[0]

        try:

            # Set restructure status to 'processing'
            document_overview.restructuring_status = (
                RestructureStatus.PROCESSING
            )

            await self.restructure_service.providers.database.relational.upsert_documents_overview(
                document_overview
            )

            errors = await self.restructure_service.kg_extract_and_store(
                document_id=document_id,
                generation_config=GenerationConfig(
                    **input_data["generation_config"]
                ),
                fragment_merge_count=fragment_merge_count,
                max_knowledge_triples=max_knowledge_triples,
                entity_types=entity_types,
                relation_types=relation_types,
            )

            # Set restructure status to 'success' if completed successfully
            if len(errors) == 0:
                document_overview.restructuring_status = (
                    RestructureStatus.SUCCESS
                )
            else:
                document_overview.restructuring_status = (
                    RestructureStatus.FAILURE
                )
                await self.restructure_service.providers.database.relational.upsert_documents_overview(
                    document_overview
                )
                raise R2RDocumentProcessingError(
                    error_message=f"Error in kg_extract_and_store, list of errors: {errors}",
                    document_id=document_id,
                )

        except Exception as e:
            # Set restructure status to 'failure' if an error occurred
            document_overview.restructuring_status = RestructureStatus.FAILURE
            await self.restructure_service.providers.database.relational.upsert_documents_overview(
                document_overview
            )
            logger.error(
                f"Error in kg_extract_and_store for document {document_id}: {str(e)}"
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

        document_ids = [
            doc.id
            for doc in await self.restructure_service.providers.database.relational.get_documents_overview()
            if doc.restructuring_status != IngestionStatus.SUCCESS
        ]

        document_ids = [str(doc_id) for doc_id in document_ids]

        documents_overviews = await self.restructure_service.providers.database.relational.get_documents_overview(
            filter_document_ids=document_ids
        )

        # Only run if restructuring_status is pending or failure
        filtered_document_ids = []
        for document_overview in documents_overviews:
            restructuring_status = document_overview.restructuring_status
            if restructuring_status in [
                RestructureStatus.PENDING,
                RestructureStatus.FAILURE,
            ]:
                filtered_document_ids.append(document_overview.id)
            elif restructuring_status == RestructureStatus.SUCCESS:
                logger.warning(
                    f"Graph already created for document ID: {document_overview.id}"
                )
            elif restructuring_status == RestructureStatus.PROCESSING:
                logger.warning(
                    f"Graph creation is already in progress for document ID: {document_overview.id}"
                )
            elif restructuring_status == RestructureStatus.ENRICHED:
                logger.warning(
                    f"Graph is already enriched for document ID: {document_overview.id}"
                )
            else:
                logger.warning(
                    f"Unknown restructuring status for document ID: {document_overview.id}"
                )

        results = []
        for document_id in filtered_document_ids:
            logger.info(
                f"Running Graph Creation Workflow for document ID: {document_id}"
            )
            results.append(
                (
                    context.aio.spawn_workflow(
                        "kg-extract-and-store",
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
                        key=f"kg-extract-and-store_{document_id}",
                    )
                )
            )

        if not filtered_document_ids:
            logger.info(
                "No documents to process, either all graphs were created or in progress, or no documents were provided. Skipping graph creation."
            )
            return {"result": "success"}

        logger.info(f"Ran {len(results)} workflows for graph creation")
        results = await asyncio.gather(*results)
        return {"result": "success"}


@r2r_hatchet.workflow(name="enrich-graph", timeout="60m")
class EnrichGraphWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=3, timeout="60m")
    async def kg_node_creation(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]
        max_description_input_length = input_data[
            "max_description_input_length"
        ]
        await self.restructure_service.kg_node_creation(
            max_description_input_length=max_description_input_length
        )
        return {"result": None}

    @r2r_hatchet.step(retries=3, parents=["kg_node_creation"], timeout="60m")
    async def kg_clustering(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]
        skip_clustering = input_data["skip_clustering"]
        force_enrichment = input_data["force_enrichment"]
        leiden_params = input_data["leiden_params"]
        max_summary_input_length = input_data["max_summary_input_length"]
        generation_config = GenerationConfig(**input_data["generation_config"])

        # todo: check if documets are already being clustered
        # check if any documents are still being restructured, need to explicitly set the force_clustering flag to true to run clustering if documents are still being restructured

        documents_overview = (
            await self.restructure_service.providers.database.relational.get_documents_overview()
        )

        if not force_enrichment:
            if any(
                document_overview.restructuring_status
                == RestructureStatus.PROCESSING
                for document_overview in documents_overview
            ):
                logger.error(
                    "Graph creation is still in progress for some documents, skipping enrichment, please set force_enrichment to true if you want to run enrichment anyway"
                )
                return {"result": None}

            if any(
                document_overview.restructuring_status
                == RestructureStatus.ENRICHING
                for document_overview in documents_overview
            ):
                logger.error(
                    "Graph enrichment is still in progress for some documents, skipping enrichment, please set force_enrichment to true if you want to run enrichment anyway"
                )
                return {"result": None}

        for document_overview in documents_overview:
            if document_overview.restructuring_status in [
                RestructureStatus.SUCCESS,
                RestructureStatus.ENRICHMENT_FAILURE,
            ]:
                document_overview.restructuring_status = (
                    RestructureStatus.ENRICHING
                )

        await self.restructure_service.providers.database.relational.upsert_documents_overview(
            documents_overview
        )

        try:
            if not skip_clustering:
                results = await self.restructure_service.kg_clustering(
                    leiden_params, generation_config
                )

                result = results[0]

                workflows = []
                for level, community_id in result["intermediate_communities"]:
                    logger.info(
                        f"Running KG Community Summary Workflow for community ID: {community_id} at level {level}"
                    )
                    workflows.append(
                        context.aio.spawn_workflow(
                            "kg-community-summary",
                            {
                                "request": {
                                    "community_id": str(community_id),
                                    "level": level,
                                    "generation_config": generation_config.to_dict(),
                                    "max_summary_input_length": max_summary_input_length,
                                }
                            },
                            key=f"kg-community-summary_{community_id}_{level}",
                        )
                    )

                results = await asyncio.gather(*workflows)
                logger.info(
                    f"KG Community Summary Workflows completed: {len(results)}"
                )

            else:
                logger.info(
                    "Skipping Leiden clustering as skip_clustering is True, also skipping community summary workflows"
                )
                return {"result": None}

        except Exception as e:
            logger.error(f"Error in kg_clustering: {str(e)}", exc_info=True)
            documents_overview = (
                await self.restructure_service.providers.database.relational.get_documents_overview()
            )
            for document_overview in documents_overview:
                if (
                    document_overview.restructuring_status
                    == RestructureStatus.ENRICHING
                ):
                    document_overview.restructuring_status = (
                        RestructureStatus.ENRICHMENT_FAILURE
                    )
                    await self.restructure_service.providers.database.relational.upsert_documents_overview(
                        document_overview
                    )
                    logger.error(
                        f"Error in kg_clustering for document {document_overview.id}: {str(e)}"
                    )

            return {"result": None}

        finally:

            documents_overview = (
                await self.restructure_service.providers.database.relational.get_documents_overview()
            )
            for document_overview in documents_overview:
                if (
                    document_overview.restructuring_status
                    == RestructureStatus.ENRICHING
                ):
                    document_overview.restructuring_status = (
                        RestructureStatus.ENRICHED
                    )

            await self.restructure_service.providers.database.relational.upsert_documents_overview(
                documents_overview
            )
            return {"result": None}


@r2r_hatchet.workflow(name="kg-community-summary", timeout="60m")
class KGCommunitySummaryWorkflow:
    def __init__(self, restructure_service: RestructureService):
        self.restructure_service = restructure_service

    @r2r_hatchet.step(retries=1, timeout="60m")
    async def kg_community_summary(self, context: Context) -> None:
        input_data = context.workflow_input()["request"]
        community_id = input_data["community_id"]
        level = input_data["level"]
        generation_config = GenerationConfig(**input_data["generation_config"])
        max_summary_input_length = input_data["max_summary_input_length"]
        await self.restructure_service.kg_community_summary(
            community_id=community_id,
            level=level,
            max_summary_input_length=max_summary_input_length,
            generation_config=generation_config,
        )
        return {"result": None}
