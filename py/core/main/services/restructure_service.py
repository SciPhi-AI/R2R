import logging
from typing import Any, Dict

from core.base import R2RException, RunLoggingSingleton, RunManager
from core.base.abstractions import KGEnrichmentSettings

from ..abstractions import R2RAgents, R2RPipelines, R2RProviders
from ..assembly.config import R2RConfig
from .base import Service

logger = logging.getLogger(__name__)


class RestructureService(Service):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: RunManager,
        logging_connection: RunLoggingSingleton,
    ):

        super().__init__(
            config,
            providers,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

    async def enrich_graph(
        self,
        enrich_graph_settings: KGEnrichmentSettings = KGEnrichmentSettings(),
    ) -> Dict[str, Any]:
        """
        Perform graph enrichment.

        Returns:
            Dict[str, Any]: Results of the graph enrichment process.
        """
        try:
            # Assuming there's a graph enrichment pipeline

            async def input_generator():
                input = []
                for doc in input:
                    yield doc

            return await self.pipelines.kg_enrichment_pipeline.run(
                input=input_generator(),
                run_manager=self.run_manager,
            )

        except Exception as e:
            logger.error(f"Error during graph enrichment: {str(e)}")
            raise R2RException(
                status_code=500, message=f"Graph enrichment failed: {str(e)}"
            )
