import logging
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    CompletionProvider,
    EmbeddingProvider,
    KGProvider,
    PipeType,
    PromptProvider,
    RunLoggingSingleton,
)

logger = logging.getLogger(__name__)


class KGClusteringPipe(AsyncPipe):
    """
    Clusters entities and triples into communities within the knowledge graph using hierarchical Leiden algorithm.
    """

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        embedding_provider: EmbeddingProvider,
        config: AsyncPipe.PipeConfig,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        *args,
        **kwargs,
    ):
        """
        Initializes the KG clustering pipe with necessary components and configurations.
        """
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config or AsyncPipe.PipeConfig(name="kg_cluster_pipe"),
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider
        self.embedding_provider = embedding_provider

    async def cluster_kg(
        self,
        collection_id: UUID,
        leiden_params: dict,
    ):
        """
        Clusters the knowledge graph triples into communities using hierarchical Leiden algorithm. Uses graspologic library.
        """

        num_communities = await self.kg_provider.perform_graph_clustering(
            collection_id,
            leiden_params,
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
