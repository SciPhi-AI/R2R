import logging
from typing import AsyncGenerator
from uuid import UUID

from core.base import KGCreationStatus, KGCreationSettings
from core.base import RunLoggingSingleton, RunManager
from core.base.abstractions import GenerationConfig
from core.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig
from shared.abstractions import KGEnrichmentSettings
from .base import Service

logger = logging.getLogger(__name__)


async def _collect_results(result_gen: AsyncGenerator) -> list[dict]:
    results = []
    async for res in result_gen:
        results.append(res.json() if hasattr(res, "json") else res)
    return results


class KgService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipes: R2RPipes,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
        logging_connection: RunLoggingSingleton,
    ):
        super().__init__(
            config,
            providers,
            pipes,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

    @telemetry_event("kg_extraction")
    async def kg_extraction(
        self,
        document_id: UUID,
        generation_config: GenerationConfig,
        extraction_merge_count: int,
        max_knowledge_triples: int,
        entity_types: list[str],
        relation_types: list[str],
        **kwargs,
    ):
        try:
            
            await self.providers.database.relational.set_workflow_status(
                id=document_id,
                status_type="kg_creation",
                status=KGCreationStatus.PROCESSING,
            )

            triples = await self.pipes.kg_extraction_pipe.run(
                input=self.pipes.kg_extraction_pipe.Input(
                    message={
                        "document_id": document_id,
                        "generation_config": generation_config,
                        "extraction_merge_count": extraction_merge_count,
                        "max_knowledge_triples": max_knowledge_triples,
                        "entity_types": entity_types,
                        "relation_types": relation_types,
                    }
                ),
                state=None,
                run_manager=self.run_manager,
            )

            result_gen = await self.pipes.kg_storage_pipe.run(
                input=self.pipes.kg_storage_pipe.Input(message=triples),
                state=None,
                run_manager=self.run_manager,
            )

            if len(triples) == 0:
                await self.providers.database.relational.set_workflow_status(
                    id=document_id,
                    status_type="kg_creation",
                    status=KGCreationStatus.SUCCESS,
                )
            else:
                raise ValueError(
                    f"Error in kg_extract_and_store: No Triples Extracted"
                )

        except Exception as e:
            logger.error(f"Error in kg_extraction: {e}")
            await self.providers.database.relational.set_workflow_status(
                id=document_id,
                status_type="kg_creation",
                status=KGCreationStatus.FAILED,
            )

        return await _collect_results(result_gen)

    @telemetry_event("get_document_ids_for_create_graph")
    async def get_document_ids_for_create_graph(
        self,
        document_ids: list[UUID],
        kg_creation_settings: KGCreationSettings,
    ):

        if not document_ids:
            document_status_filter = [
                KGCreationStatus.PENDING,
                KGCreationStatus.FAILED,
            ]
            if kg_creation_settings.force_kg_creation:
                document_status_filter += [
                    KGCreationStatus.SUCCESS,
                    KGCreationStatus.PROCESSING,
                ]

            document_ids = await self.providers.database.relational.get_document_ids_by_status(
                status_type="kg_creation", status=document_status_filter
            )

        return document_ids

    @telemetry_event("kg_node_description")
    async def kg_node_description(
        self,
        project_name: str,
        document_id: UUID,
        max_description_input_length: int,
    ):
        
        entity_count = await self.providers.kg.get_entity_count(
            **input_data
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
                max_description_input_length=input_data["max_description_input_length"],
                project_name=input_data["project_name"],
            )



        node_extractions = await self.pipes.kg_node_description_pipe.run(
            input=self.pipes.kg_node_description_pipe.Input(
                message={
                    "offset": offset,
                    "limit": limit,
                    "max_description_input_length": max_description_input_length,
                    "project_name": project_name,
                }
            ),
            state=None,
            run_manager=self.run_manager,
        )
        return await _collect_results(node_extractions)

    @telemetry_event("kg_clustering")
    async def kg_clustering(
        self,
        collection_id: UUID,
        kg_enrichment_settings: KGEnrichmentSettings,
        project_name: str,
    ):
        clustering_result = await self.pipes.kg_clustering_pipe.run(
            input=self.pipes.kg_clustering_pipe.Input(
                message={
                    "project_name": project_name,
                    "collection_id": collection_id,
                    "kg_enrichment_settings": kg_enrichment_settings,
                }
            ),
            state=None,
            run_manager=self.run_manager,
        )
        return await _collect_results(clustering_result)

    @telemetry_event("kg_community_summary")
    async def kg_community_summary(
        self,
        offset: int,
        limit: int,
        max_summary_input_length: int,
        generation_config: GenerationConfig,
        project_name: str,
        collection_id: UUID,
        **kwargs,
    ):
        summary_results = await self.pipes.kg_community_summary_pipe.run(
            input=self.pipes.kg_community_summary_pipe.Input(
                message={
                    "offset": offset,
                    "limit": limit,
                    "generation_config": generation_config,
                    "max_summary_input_length": max_summary_input_length,
                    "project_name": project_name,
                    "collection_id": collection_id,
                }
            ),
            state=None,
            run_manager=self.run_manager,
        )
        return await _collect_results(summary_results)
