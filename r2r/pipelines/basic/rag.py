"""
A simple example to demonstrate the usage of `BasicRAGPipeline`.
"""
import logging
from typing import Optional

from r2r.core import (
    GenerationConfig,
    LLMProvider,
    LoggingDatabaseConnection,
    RAGPipeline,
    VectorDBProvider,
    VectorSearchResult,
    log_execution_to_db,
)
from r2r.embeddings import OpenAIEmbeddingProvider

logger = logging.getLogger(__name__)


class BasicRAGPipeline(RAGPipeline):
    """
    Implements a basic Retrieve-And-Generate (RAG) pipeline for document retrieval and generation.
    """

    def __init__(
        self,
        llm: LLMProvider,
        generation_config: GenerationConfig,
        db: VectorDBProvider,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
        logging_provider: Optional[LoggingDatabaseConnection] = None,
        system_prompt: Optional[str] = None,
        task_prompt: Optional[str] = None,
    ) -> None:
        """
        Initializes the RAG pipeline with necessary components and configurations.
        """
        logger.debug(f"Initalizing `BasicRAGPipeline`.")

        super().__init__(
            llm,
            generation_config,
            logging_provider=logging_provider,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
        )
        self.embedding_model = embedding_model
        self.embeddings_provider = embeddings_provider
        self.db = db
        self.pipeline_run_info = None

    def transform_query(self, query: str) -> str:
        """
        Transforms the input query before retrieval, if necessary.
        """
        self._check_pipeline_initialized()
        return query

    @log_execution_to_db
    def search(
        self,
        transformed_query: str,
        filters: dict,
        limit: int,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        """
        Searches the vector database with the transformed query to retrieve relevant documents.
        """
        logger.debug(f"Retrieving results for query: {transformed_query}")
        self._check_pipeline_initialized()
        results = self.db.search(
            query_vector=self.embeddings_provider.get_embedding(
                transformed_query,
                self.embedding_model,
            ),
            filters=filters,
            limit=limit,
        )
        logger.debug(f"Retrieved the raw results shown:\n{results}\n")

        return results

    def rerank_results(
        self, results: list[VectorSearchResult]
    ) -> list[VectorSearchResult]:
        """
        Reranks the retrieved documents based on relevance, if necessary.
        """
        self._check_pipeline_initialized()
        # Placeholder for reranking logic - A unit transformation.
        return results

    def _format_results(self, results: list[VectorSearchResult]) -> str:
        """
        Formats the reranked results into a human-readable string.
        """
        return "\n\n".join([ele.metadata["text"] for ele in results])

    def _get_extra_args(self, *args, **kwargs):
        """
        Retrieves any extra arguments needed for the pipeline's operations.
        """
        return {}
