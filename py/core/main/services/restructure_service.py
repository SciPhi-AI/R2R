import logging
from typing import AsyncGenerator
from uuid import UUID

from core.base import RunLoggingSingleton, RunManager
from core.base.abstractions import GenerationConfig
from core.telemetry.telemetry_decorator import telemetry_event

from ..abstractions import R2RAgents, R2RPipelines, R2RPipes, R2RProviders
from ..config import R2RConfig
from .base import Service

logger = logging.getLogger(__name__)


async def _collect_results(result_gen: AsyncGenerator) -> list[dict]:
    results = []
    async for res in result_gen:
        results.append(res.json() if hasattr(res, "json") else res)
    return results


class RestructureService(Service):
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

    @telemetry_event("kg_extract_and_store")
    async def kg_extract_and_store(
        self,
        document_id: UUID,
        generation_config: GenerationConfig,
        fragment_merge_count: int,
        max_knowledge_triples: int,
        entity_types: list[str],
        relation_types: list[str],
    ):
        triples = await self.pipes.kg_extraction_pipe.run(
            input=self.pipes.kg_extraction_pipe.Input(
                message={
                    "document_id": document_id,
                    "generation_config": generation_config,
                    "fragment_merge_count": fragment_merge_count,
                    "max_knowledge_triples": max_knowledge_triples,
                    "entity_types": entity_types,
                    "relation_types": relation_types,
                }
            ),
            run_manager=self.run_manager,
        )

        result_gen = await self.pipes.kg_storage_pipe.run(
            input=self.pipes.kg_storage_pipe.Input(message=triples),
            run_manager=self.run_manager,
        )

        return await _collect_results(result_gen)

    @telemetry_event("kg_node_creation")
    async def kg_node_creation(self, max_description_input_length: int):
        node_extrations = await self.pipes.kg_node_extraction_pipe.run(
            input=self.pipes.kg_node_extraction_pipe.Input(message=None),
            run_manager=self.run_manager,
        )
        result_gen = await self.pipes.kg_node_description_pipe.run(
            input=self.pipes.kg_node_description_pipe.Input(
                message={
                    "node_extrations": node_extrations,
                    "max_description_input_length": max_description_input_length,
                }
            ),
            run_manager=self.run_manager,
        )
        return await _collect_results(result_gen)

    @telemetry_event("kg_clustering")
    async def kg_clustering(self, leiden_params, generation_config):
        clustering_result = await self.pipes.kg_clustering_pipe.run(
            input=self.pipes.kg_clustering_pipe.Input(
                message={
                    "leiden_params": leiden_params,
                    "generation_config": generation_config,
                }
            ),
            run_manager=self.run_manager,
        )

        return await _collect_results(clustering_result)

    @telemetry_event("kg_community_summary")
    async def kg_community_summary(
        self,
        community_id: str,
        level: int,
        max_summary_input_length: int,
        generation_config: GenerationConfig,
    ):
        summary_results = await self.pipes.kg_community_summary_pipe.run(
            input=self.pipes.kg_community_summary_pipe.Input(
                message={
                    "community_id": community_id,
                    "level": level,
                    "generation_config": generation_config,
                    "max_summary_input_length": max_summary_input_length,
                }
            ),
            run_manager=self.run_manager,
        )
        return await _collect_results(summary_results)
