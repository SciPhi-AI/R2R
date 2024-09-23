import logging
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    CompletionProvider,
    EmbeddingProvider,
    GenerationConfig,
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
        leiden_params: dict,
        generation_config: GenerationConfig,
    ):
        """
        Clusters the knowledge graph triples into communities using hierarchical Leiden algorithm. Uses neo4j's graph data science library.
        """

        num_communities, num_hierarchies, intermediate_communities = (
            self.kg_provider.perform_graph_clustering(leiden_params)  # type: ignore
        )

        logger.info(
            f"Clustering completed. Generated {num_communities} communities with {num_hierarchies} hierarchies with intermediate communities: {intermediate_communities}."
        )

        return {
            "num_communities": num_communities,
            "num_hierarchies": num_hierarchies,
            "intermediate_communities": intermediate_communities,
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

        leiden_params = input.message["leiden_params"]
        if not leiden_params:
            raise ValueError("Leiden parameters not provided.")
        generation_config = input.message["generation_config"]
        if not generation_config:
            raise ValueError("Generation config not provided.")

        base_dimension = self.embedding_provider.config.base_dimension
        vector_index_fn = self.kg_provider.create_vector_index
        vector_index_fn("__ENTITY__", "name_embedding", base_dimension)
        vector_index_fn("__ENTITY__", "description_embedding", base_dimension)
        vector_index_fn("__RELATIONSHIP__", "description", base_dimension)
        vector_index_fn("__Community__", "summary_embedding", base_dimension)

        yield await self.cluster_kg(leiden_params, generation_config)
