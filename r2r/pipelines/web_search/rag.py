"""
A simple example to demonstrate the usage of `WebSearchRAGPipeline`.
"""
import logging
from typing import Optional

from r2r.core import (
    GenerationConfig,
    LLMProvider,
    LoggingDatabaseConnection,
    VectorDBProvider,
    log_execution_to_db,
)
from r2r.embeddings import OpenAIEmbeddingProvider
from r2r.integrations import SerperClient

from ..basic.rag import BasicRAGPipeline

logger = logging.getLogger(__name__)


class WebSearchRAGPipeline(BasicRAGPipeline):
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
        logger.debug(f"Initalizing `WebSearchRAGPipeline`.")
        super().__init__(
            llm=llm,
            generation_config=generation_config,
            logging_provider=logging_provider,
            db=db,
            embedding_model=embedding_model,
            embeddings_provider=embeddings_provider,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
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
        *args,
        **kwargs,
    ) -> list:
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
