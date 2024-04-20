"""
A simple example to demonstrate the usage of `QnARAGPipeline`.
"""

import logging
from typing import Optional

from r2r.core import (
    EmbeddingProvider,
    LLMProvider,
    LoggingDatabaseConnection,
    PromptProvider,
    RAGPipeline,
    VectorDBProvider,
    VectorSearchResult,
    log_execution_to_db,
)

from ..core.prompt_provider import BasicPromptProvider

logger = logging.getLogger(__name__)


class QnARAGPipeline(RAGPipeline):
    """
    Implements a basic question and answer Retrieval-Augmented-Generation (RAG) pipeline.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        llm_provider: LLMProvider,
        vector_db_provider: VectorDBProvider,
        prompt_provider: Optional[PromptProvider] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
    ) -> None:
        """
        Initializes the RAG pipeline with necessary components and configurations.
        """
        logger.debug(f"Initalizing `QnARAGPipeline`.")
        if not prompt_provider:
            prompt_provider = BasicPromptProvider()
        self.prompt_provider = prompt_provider

        super().__init__(
            prompt_provider=prompt_provider,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
            vector_db_provider=vector_db_provider,
            logging_connection=logging_connection,
        )
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
        results = self.vector_db_provider.search(
            query_vector=self.embedding_provider.get_embedding(
                transformed_query,
            ),
            filters=filters,
            limit=limit,
        )

        logger.debug(f"Retrieved the raw results shown:\n{results}\n")

        return results

    def rerank_results(
        self,
        transformed_query: str,
        results: list[VectorSearchResult],
        limit: int,
    ) -> list[VectorSearchResult]:
        """
        Reranks the retrieved documents based on relevance, if necessary.
        """
        self._check_pipeline_initialized()
        return self.embedding_provider.rerank(
            transformed_query, results, limit=limit
        )

    def _format_results(self, results: list[VectorSearchResult]) -> str:
        """
        Formats the reranked results into a human-readable string.
        """
        return "\n\n".join([ele.metadata["text"] for ele in results])
