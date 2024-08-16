import logging
from typing import Any, Dict, List

from r2r.base import Document, R2RException, RunLoggingSingleton, RunManager

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
        self, documents: List[Document] = None
    ) -> Dict[str, Any]:
        """
        Perform graph enrichment on the given documents.

        Args:
            documents (List[Document]): List of documents to enrich.

        Returns:
            Dict[str, Any]: Results of the graph enrichment process.
        """
        try:
            # Assuming there's a graph enrichment pipeline
            enrichment_results = await self.pipelines.kg_pipeline.run(
                input=[],
                run_manager=self.run_manager,
            )

            return enrichment_results

        except Exception as e:
            logger.error(f"Error during graph enrichment: {str(e)}")
            raise R2RException(
                status_code=500, message=f"Graph enrichment failed: {str(e)}"
            )

    async def query_graph(self, query: str) -> Dict[str, Any]:
        """
        Query the knowledge graph.

        Args:
            query (str): The query to run against the knowledge graph.

        Returns:
            Dict[str, Any]: Results of the graph query.
        """
        try:
            results = self.providers.database.graph.query(query)
            return {"results": results}
        except Exception as e:
            logger.error(f"Error querying graph: {str(e)}")
            raise R2RException(
                status_code=500, message=f"Graph query failed: {str(e)}"
            )

    async def get_graph_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge graph.

        Returns:
            Dict[str, Any]: Statistics about the knowledge graph.
        """
        try:
            stats = self.providers.database.graph.get_statistics()
            return stats
        except Exception as e:
            logger.error(f"Error getting graph statistics: {str(e)}")
            raise R2RException(
                status_code=500,
                message=f"Failed to retrieve graph statistics: {str(e)}",
            )
