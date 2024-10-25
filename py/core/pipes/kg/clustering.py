import logging
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    CompletionProvider,
    DatabaseProvider,
    EmbeddingProvider,
)
from core.providers.logging.r2r_logging import SqlitePersistentLoggingProvider

logger = logging.getLogger()


class KGClusteringPipe(AsyncPipe):
    """
    Clusters entities and triples into communities within the knowledge graph using hierarchical Leiden algorithm.
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
        config: AsyncPipe.PipeConfig,
        logging_provider: SqlitePersistentLoggingProvider,
        *args,
        **kwargs,
    ):
        """
        Initializes the KG clustering pipe with necessary components and configurations.
        """
        super().__init__(
            logging_provider=logging_provider,
            config=config or AsyncPipe.PipeConfig(name="kg_cluster_pipe"),
        )
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def cluster_kg(
        self,
        collection_id: UUID,
        leiden_params: dict,
    ):
        """
        Clusters the knowledge graph triples into communities using hierarchical Leiden algorithm. Uses graspologic library.
        """

        num_communities = (
            await self.database_provider.perform_graph_clustering(
                collection_id,
                leiden_params,
            )
        )  # type: ignore

        logger.info(
            f"Clustering completed. Generated {num_communities} communities."
        )

        return {
            "num_communities": num_communities,
        }

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[dict, None]:
        """
        Executes the KG clustering pipe: clustering entities and triples into communities.
        """

        collection_id = input.message["collection_id"]
        leiden_params = input.message["leiden_params"]

        yield await self.cluster_kg(collection_id, leiden_params)
