"""
A simple example to demonstrate the usage of `BasicRAGPipeline`.
"""

import logging
from typing import Optional

from r2r.core import (
    LLMProvider,
    LoggingDatabaseConnection,
    PromptProvider,
    RAGPipeline,
    VectorDBProvider,
    VectorSearchResult,
    log_execution_to_db,
)
from r2r.embeddings import OpenAIEmbeddingProvider

from .prompt_provider import BasicPromptProvider

logger = logging.getLogger(__name__)


class BasicRAGPipeline(RAGPipeline):
    """
    Implements a basic Retrieve-And-Generate (RAG) pipeline for document retrieval and generation.
    """

    def __init__(
        self,
        llm: LLMProvider,
        db: VectorDBProvider,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
        prompt_provider: Optional[PromptProvider] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
    ) -> None:
        """
        Initializes the RAG pipeline with necessary components and configurations.
        """
        logger.debug(f"Initalizing `BasicRAGPipeline`.")
        if not prompt_provider:
            prompt_provider = BasicPromptProvider()
        self.prompt_provider = prompt_provider

        super().__init__(
            llm,
            prompt_provider=prompt_provider,
            logging_connection=logging_connection,
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
