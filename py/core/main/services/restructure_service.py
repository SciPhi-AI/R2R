import json
import logging
from uuid import UUID
from typing import Any, AsyncGenerator, Dict, Optional, Union

from core.base import R2RException, RunLoggingSingleton, RunManager
from core.base.abstractions import KGCreationSettings, KGEnrichmentSettings, GenerationConfig

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

    async def kg_extract_and_store(
        self, document_id: UUID, generation_config: GenerationConfig
    ):
        triples = await self.pipes.kg_extraction_pipe.run(
            input=self.pipes.kg_extraction_pipe.Input(
                message = {
                    "document_id": document_id,
                    "generation_config": generation_config
                }
            ),
            run_manager=self.run_manager,
        )
        result_gen = await self.pipes.kg_storage_pipe.run(
            input=self.pipes.kg_storage_pipe.Input(message=triples),
            run_manager=self.run_manager,
        )

        return await _collect_results(result_gen)

    async def kg_node_creation(self):
        node_extrations = await self.pipes.kg_node_extraction_pipe.run(
            input=self.pipes.kg_node_extraction_pipe.Input(message=None),
            run_manager=self.run_manager,
        )
        result_gen = await self.pipes.kg_node_description_pipe.run(
            input=self.pipes.kg_node_description_pipe.Input(
                message=node_extrations
            ),
            run_manager=self.run_manager,
        )
        return await _collect_results(result_gen)

    async def kg_clustering(self, leiden_params, generation_config):
        result_gen = await self.pipes.kg_clustering_pipe.run(
            input=self.pipes.kg_clustering_pipe.Input(message={
                "leiden_params": leiden_params,
                "generation_config": generation_config
            }),
            run_manager=self.run_manager,
        )
        return await _collect_results(result_gen)