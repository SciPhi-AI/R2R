import asyncio
import json
import logging
import uuid

from core import GenerationConfig, IngestionStatus, KGCreationSettings
from core.base import R2RDocumentProcessingError
from core.base.abstractions import RestructureStatus

from ...services import RestructureService

logger = logging.getLogger(__name__)


def simple_restructure_factory(service: RestructureService):

    async def kg_extract_and_store(input_data):
        document_id = uuid.UUID(input_data["document_id"])
        fragment_merge_count = input_data["fragment_merge_count"]
        max_knowledge_triples = input_data["max_knowledge_triples"]
        entity_types = input_data["entity_types"]
        relation_types = input_data["relation_types"]

        document_overview = (
            await service.providers.database.relational.get_documents_overview(
                filter_document_ids=[document_id]
            )
        )
        document_overview = document_overview["results"][0]

        try:
            # Set restructure status to 'processing'
            document_overview.restructuring_status = (
                RestructureStatus.PROCESSING
            )
            await service.providers.database.relational.upsert_documents_overview(
                document_overview
            )

            errors = await service.kg_extract_and_store(
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
                await service.providers.database.relational.upsert_documents_overview(
                    document_overview
                )
            else:
                document_overview.restructuring_status = (
                    RestructureStatus.FAILURE
                )
                await service.providers.database.relational.upsert_documents_overview(
                    document_overview
                )
                raise R2RDocumentProcessingError(
                    error_message=f"Error in kg_extract_and_store, list of errors: {errors}",
                    document_id=document_id,
                )

        except Exception as e:
            # Set restructure status to 'failure' if an error occurred
            document_overview.restructuring_status = RestructureStatus.FAILURE
            await service.providers.database.relational.upsert_documents_overview(
                document_overview
            )
            raise R2RDocumentProcessingError(
                error_message=e,
                document_id=document_id,
            )

    async def create_graph(input_data):
        kg_creation_settings = KGCreationSettings(
            **json.loads(input_data["kg_creation_settings"])
        )

        documents_overview = (
            await service.providers.database.relational.get_documents_overview()
        )
        documents_overview = documents_overview["results"]

        document_ids = [
            doc.id
            for doc in documents_overview
            if doc.restructuring_status != IngestionStatus.SUCCESS
        ]

        document_ids = [str(doc_id) for doc_id in document_ids]

        documents_overviews = (
            await service.providers.database.relational.get_documents_overview(
                filter_document_ids=document_ids
            )
        )
        documents_overviews = documents_overviews["results"]

        # Only run if restructuring_status is pending or failure
        filtered_document_ids = []
        for document_overview in documents_overviews:
            restructuring_status = document_overview.restructuring_status
            if restructuring_status in [
                RestructureStatus.PENDING,
                RestructureStatus.FAILURE,
                RestructureStatus.ENRICHMENT_FAILURE,
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
                kg_extract_and_store(
                    {
                        "document_id": str(document_id),
                        "fragment_merge_count": kg_creation_settings.fragment_merge_count,
                        "max_knowledge_triples": kg_creation_settings.max_knowledge_triples,
                        "generation_config": kg_creation_settings.generation_config.to_dict(),
                        "entity_types": kg_creation_settings.entity_types,
                        "relation_types": kg_creation_settings.relation_types,
                    }
                )
            )

        if not filtered_document_ids:
            logger.info(
                "No documents to process, either all graphs were created or in progress, or no documents were provided. Skipping graph creation."
            )
            return

        logger.info(f"Ran {len(results)} workflows for graph creation")
        await asyncio.gather(*results)

    async def enrich_graph(input_data):
        max_description_input_length = input_data[
            "max_description_input_length"
        ]
        await service.kg_node_creation(
            max_description_input_length=max_description_input_length
        )

        skip_clustering = input_data["skip_clustering"]
        force_enrichment = input_data["force_enrichment"]
        leiden_params = input_data["leiden_params"]
        max_summary_input_length = input_data["max_summary_input_length"]
        generation_config = GenerationConfig(**input_data["generation_config"])

        documents_overview = (
            await service.providers.database.relational.get_documents_overview()
        )
        documents_overview = documents_overview["results"]

        if not force_enrichment:
            if any(
                document_overview.restructuring_status
                == RestructureStatus.PROCESSING
                for document_overview in documents_overview
            ):
                logger.error(
                    "Graph creation is still in progress for some documents, skipping enrichment, please set force_enrichment to true if you want to run enrichment anyway"
                )
                return

            if any(
                document_overview.restructuring_status
                == RestructureStatus.ENRICHING
                for document_overview in documents_overview
            ):
                logger.error(
                    "Graph enrichment is still in progress for some documents, skipping enrichment, please set force_enrichment to true if you want to run enrichment anyway"
                )
                return

        for document_overview in documents_overview:
            if document_overview.restructuring_status in [
                RestructureStatus.SUCCESS,
                RestructureStatus.ENRICHMENT_FAILURE,
            ]:
                document_overview.restructuring_status = (
                    RestructureStatus.ENRICHING
                )

        await service.providers.database.relational.upsert_documents_overview(
            documents_overview
        )

        try:
            if not skip_clustering:
                results = await service.kg_clustering(
                    leiden_params, generation_config
                )
                result = results[0]

                # Run community summary workflows
                workflows = []
                for level, community_id in result["intermediate_communities"]:
                    logger.info(
                        f"Running KG Community Summary Workflow for community ID: {community_id} at level {level}"
                    )
                    workflows.append(
                        kg_community_summary(
                            {
                                "community_id": str(community_id),
                                "level": level,
                                "generation_config": generation_config.to_dict(),
                                "max_summary_input_length": max_summary_input_length,
                            }
                        )
                    )

                await asyncio.gather(*workflows)
            else:
                logger.info(
                    "Skipping Leiden clustering as skip_clustering is True, also skipping community summary workflows"
                )

        except Exception as e:
            logger.error(f"Error in kg_clustering: {str(e)}", exc_info=True)
            documents_overview = (
                await service.providers.database.relational.get_documents_overview()
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
                    await service.providers.database.relational.upsert_documents_overview(
                        document_overview
                    )
                    logger.error(
                        f"Error in kg_clustering for document {document_overview.id}: {str(e)}"
                    )
            raise e

        finally:
            documents_overview = (
                await service.providers.database.relational.get_documents_overview()
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

            await service.providers.database.relational.upsert_documents_overview(
                documents_overview
            )

    async def kg_community_summary(input_data):
        community_id = input_data["community_id"]
        level = input_data["level"]
        generation_config = GenerationConfig(**input_data["generation_config"])
        max_summary_input_length = input_data["max_summary_input_length"]
        await service.kg_community_summary(
            community_id=community_id,
            level=level,
            max_summary_input_length=max_summary_input_length,
            generation_config=generation_config,
        )

    return {
        "kg-extract-and-store": kg_extract_and_store,
        "create-graph": create_graph,
        "enrich-graph": enrich_graph,
        "kg-community-summary": kg_community_summary,
    }
