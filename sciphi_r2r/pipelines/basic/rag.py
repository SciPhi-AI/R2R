"""
A simple example to demonstrate the usage of `BasicRAGPipeline`.
"""
import logging
from typing import Optional

from sciphi_r2r.core import (
    GenerationConfig,
    LLMProvider,
    LoggingDatabaseConnection,
    RAGPipeline,
    SearchResult,
    log_execution_to_db,
)
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider
from sciphi_r2r.vector_dbs import PGVectorDB

logger = logging.getLogger(__name__)


class BasicRAGPipeline(RAGPipeline):
    def __init__(
        self,
        llm: LLMProvider,
        generation_config: GenerationConfig,
        logging_database: LoggingDatabaseConnection,
        db: PGVectorDB,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
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
    def retrieve_chunks(
        self,
        transformed_query: str,
        filters: dict,
        limit: int,
        search_type="semantic",
    ) -> list[SearchResult]:
        logger.debug(f"Retrieving chunks for query: {transformed_query}")

        results = self.db.search(
            query_vector=self.embeddings_provider.get_embedding(
                transformed_query,
                self.embedding_model,
            ),
            filters=filters,
            limit=limit,
        )
        logger.debug(f"Retrieved the raw chunks shown:\n{results}\n")
        return results

    def rerank_chunks(self, chunks: list[SearchResult]) -> list[SearchResult]:
        # Placeholder for reranking logic - A unit transformation.
        return chunks

    def _format_chunks(self, chunks: list[SearchResult]) -> str:
        return "\n\n".join([ele.metadata["text"] for ele in chunks])

    def _get_extra_args(self, query, context):
        return {}
