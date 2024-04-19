"""
A simple example to demonstrate the usage of `WebSearchRAGPipeline`.
"""

import json
import logging
from typing import Generator, Optional

from r2r.core import (
    GenerationConfig,
    LLMProvider,
    LoggingDatabaseConnection,
    RAGPipeline,
    VectorDBProvider,
    log_execution_to_db,
)
from r2r.embeddings import OpenAIEmbeddingProvider
from r2r.integrations import SerperClient
from ..core.prompt_provider import BasicPromptProvider
from ..qna.rag import QnARAGPipeline

WEB_RAG_SYSTEM_PROMPT = "You are a helpful assistant."
WEB_RAG_TASK_PROMPT = """
## Task:
Answer the query given immediately below given the context which follows later. Use line item references to like [1], [2], ... refer to specifically numbered items in the provided context. Pay close attention to the title of each given source to ensure it is consistent with the query.

### Query:
{query}

### Context:
{context}

### Query:
{query}

REMINDER - Use line item references to like [1], [2], ... refer to specifically numbered items in the provided context.
## Response:
"""
logger = logging.getLogger(__name__)


class WebRAGPipeline(QnARAGPipeline):
    def __init__(
        self,
        llm: LLMProvider,
        db: VectorDBProvider,
        embedding_model: str,
        embeddings_provider: OpenAIEmbeddingProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        prompt_provider: Optional[BasicPromptProvider] = BasicPromptProvider(
            WEB_RAG_SYSTEM_PROMPT, WEB_RAG_TASK_PROMPT
        ),
    ) -> None:
        logger.debug(f"Initalizing `WebRAGPipeline`.")
        super().__init__(
            llm=llm,
            logging_connection=logging_connection,
            db=db,
            embedding_model=embedding_model,
            embeddings_provider=embeddings_provider,
            prompt_provider=prompt_provider,
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

        return external_results

    @log_execution_to_db
    def construct_context(self, results: list) -> str:
        local_context = super().construct_context(
            [ele["result"] for ele in results if ele["type"] == "local"]
        )
        web_context = self.serper_client.construct_context(
            [ele["result"] for ele in results if ele["type"] == "external"]
        )
        return local_context + "\n\n" + web_context

    def _stream_run(
        self,
        search_results: list,
        context: str,
        prompt: str,
        generation_config: GenerationConfig,
    ) -> Generator[str, None, None]:
        yield f"<{RAGPipeline.SEARCH_STREAM_MARKER}>"
        yield json.dumps(search_results)
        yield f"</{RAGPipeline.SEARCH_STREAM_MARKER}>"

        yield f"<{RAGPipeline.CONTEXT_STREAM_MARKER}>"
        yield context
        yield f"</{RAGPipeline.CONTEXT_STREAM_MARKER}>"
        yield f"<{RAGPipeline.COMPLETION_STREAM_MARKER}>"
        for chunk in self.generate_completion(prompt, generation_config):
            yield chunk
        yield f"</{RAGPipeline.COMPLETION_STREAM_MARKER}>"
