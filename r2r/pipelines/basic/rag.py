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
    def __init__(
        self,
        llm: LLMProvider,
        generation_config: GenerationConfig,
        db: VectorDBProvider,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
        logging_database: Optional[LoggingDatabaseConnection] = None,
        system_prompt: Optional[str] = None,
        task_prompt: Optional[str] = None,
    ) -> None:
        logger.debug(f"Initalizing `BasicRAGPipeline`.")

        super().__init__(
            llm,
            generation_config,
            logging_database=logging_database,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
        )
        self.embedding_model = embedding_model
        self.embeddings_provider = embeddings_provider
        self.db = db

    def transform_query(self, query: str) -> str:
        # Placeholder for query transformation - A unit transformation.
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
        logger.debug(f"Retrieving results for query: {transformed_query}")

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
        # Placeholder for reranking logic - A unit transformation.
        return results

    def _format_results(self, results: list[VectorSearchResult]) -> str:
        return "\n\n".join([ele.metadata["text"] for ele in results])

    def _get_extra_args(self, *args, **kwargs):
        return {}
