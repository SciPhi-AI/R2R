import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    CompletionProvider,
    EmbeddingProvider,
)

# from ...database.postgres import PostgresDatabaseProvider
from core.database import PostgresDatabaseProvider

logger = logging.getLogger()


class KGClusteringPipe(AsyncPipe):
    """
    Clusters entities and relationships into communities within the knowledge graph using hierarchical Leiden algorithm.
    """

    def __init__(
        self,
        database_provider: PostgresDatabaseProvider,
        llm_provider: CompletionProvider,
        embedding_provider: EmbeddingProvider,
        config: AsyncPipe.PipeConfig,
        *args,
        **kwargs,
    ):
        """
        Initializes the KG clustering pipe with necessary components and configurations.
        """
        super().__init__(
            config=config or AsyncPipe.PipeConfig(name="kg_cluster_pipe"),
        )
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def cluster_kg(
        self,
        collection_id: UUID,
        leiden_params: dict,
        clustering_mode: str,
    ):
        """
        Clusters the knowledge graph relationships into communities using hierarchical Leiden algorithm. Uses graspologic library.
        """

        num_communities = await self.database_provider.graphs_handler.perform_graph_clustering(
            collection_id=collection_id,
            leiden_params=leiden_params,
            clustering_mode=clustering_mode,
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
        Executes the KG clustering pipe: clustering entities and relationships into communities.
        """

        collection_id = input.message.get("collection_id", None)
        leiden_params = input.message["leiden_params"]
        clustering_mode = input.message["clustering_mode"]

        yield await self.cluster_kg(
            collection_id=collection_id,
            leiden_params=leiden_params,
            clustering_mode=clustering_mode,
        )
