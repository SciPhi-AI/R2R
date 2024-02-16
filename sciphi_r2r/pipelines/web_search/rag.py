"""
A simple example to demonstrate the usage of `WebSearchRAGPipeline`.
"""
import logging
from typing import Optional

from sciphi_r2r.core import (GenerationConfig, LLMProvider,
                             LoggingDatabaseConnection, RAGPipeline,
                             VectorSearchResult, log_execution_to_db)
from sciphi_r2r.embeddings import OpenAIEmbeddingProvider
from sciphi_r2r.integrations import SerperClient
from sciphi_r2r.vector_dbs import PGVectorDB

from ..basic.rag import BasicRAGPipeline

logger = logging.getLogger(__name__)


class WebSearchRAGPipeline(BasicRAGPipeline):
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
            logging_database,
            db,
            embedding_model,
            embeddings_provider,
            system_prompt,
            task_prompt,
        )
        self.serper_client = SerperClient()

    def transform_query(self, query: str) -> str:
        # Placeholder for query transformation - A unit transformation.
        return query

    @log_execution_to_db
    def search(
        self,
        transformed_query: str,
        filters: dict,
        limit: int,
        search_type="semantic",
    ) -> list[VectorSearchResult]:
        results = []
        local_results = super().search(transformed_query, filters, limit)
        results.extend(
            [{"type": "local", "result": ele} for ele in local_results]
        )

        external_results = self.serper_client.get_raw(transformed_query, limit)
        results.extend(
            [{"type": "external", "result": ele} for ele in external_results]
        )

        return results

    @log_execution_to_db
    def construct_context(self, results: list) -> str:
        local_context = super().construct_context(
            [ele["result"] for ele in results if ele["type"] == "local"]
        )
        web_context = self.serper_client.construct_context(
            [ele["result"] for ele in results if ele["type"] == "external"]
        )
        return local_context + "\n\n" + web_context
