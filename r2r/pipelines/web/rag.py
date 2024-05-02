"""
A simple example to demonstrate the usage of `WebRAGPipeline`.
"""

import logging
import uuid
from typing import Generator, Optional, Union

from r2r.core import (
    GenerationConfig,
    LLMChatCompletion,
    LLMProvider,
    LoggingDatabaseConnection,
    RAGPipeline,
    RAGPipelineOutput,
    VectorDBProvider,
    VectorSearchResult,
    log_execution_to_db,
)
from r2r.embeddings import OpenAIEmbeddingProvider
from r2r.integrations import SerperClient

from ...prompts import BasicPromptProvider

WEB_RAG_SYSTEM_PROMPT = "You are a helpful assistant."
WEB_RAG_RETURN_PROMPT = """
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


class WebRAGPipeline(RAGPipeline):
    def __init__(
        self,
        llm_provider: LLMProvider,
        embedding_provider: OpenAIEmbeddingProvider,
        vector_db_provider: VectorDBProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        prompt_provider: Optional[BasicPromptProvider] = BasicPromptProvider(
            WEB_RAG_SYSTEM_PROMPT, WEB_RAG_RETURN_PROMPT
        ),
    ) -> None:
        logger.info(f"Initalizing `WebRAGPipeline` to process user requests.")
        super().__init__(
            llm_provider=llm_provider,
            vector_db_provider=vector_db_provider,
            embedding_provider=embedding_provider,
            prompt_provider=prompt_provider,
            logging_connection=logging_connection,
        )
        self.serper_client = SerperClient()

    def transform_message(
        self, query: str, generation_config: Optional[GenerationConfig] = None
    ) -> str:
        # Placeholder for query transformation - A unit transformation.
        return query

    @log_execution_to_db
    def search(
        self,
        query: str,
        filters: dict,
        limit: int,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        """Perform a search using the Serper API and return results in the expected format."""
        serper_results = self.serper_client.get_raw(query, limit)
        vector_search_results = []
        counter = 0
        for result in serper_results:
            score = result.pop(
                "score", 1.0
            )  # Defaulting score to 1.0 if not present
            entry_id = result.get("title") or str(
                uuid.uuid4()
            )  # Use title if present, otherwise generate a random UUID
            snippet = result.get("snippet")
            if not snippet:
                continue
            # Create a VectorSearchResult object for each result
            vector_search_result = VectorSearchResult(
                entry_id=entry_id,  # Using 'title' as a unique identifier
                score=score,
                metadata=result,  # Storing the entire result as metadata
            )
            vector_search_results.append(vector_search_result)
            counter += 1
            if counter >= limit:
                break

        local_results = super().search(
            query=query,
            filters=filters,
            limit=limit,
        )[0:limit]
        for result in local_results:
            vector_search_results.append(result)
        print("vector_search_results = ", vector_search_results)

        return vector_search_results

    def run(
        self,
        message,
        generation_config: GenerationConfig,
        filters={},
        search_limit=25,
        rerank_limit=15,
        *args,
        **kwargs,
    ) -> Union[RAGPipelineOutput, LLMChatCompletion]:
        """
        Run the RAG pipeline in streaming mode.
        """
        search_limit = rerank_limit
        rerank_limit = 2 * rerank_limit
        return super().run(
            message=message,
            generation_config=generation_config,
            filters=filters,
            search_limit=search_limit,
            rerank_limit=rerank_limit,
        )

    def _format_results(self, results: list[VectorSearchResult]) -> str:
        """
        Formats the reranked results into a human-readable string.
        """
        context = ""
        for it, ele in enumerate(results):
            metadata = ele.metadata
            print("ele = ", ele)
            if "link" in metadata:
                context += f"\n\n{it+1} - {metadata['title']} ({metadata['link']})\n{metadata['snippet']}\n\n"
            elif "text" in metadata:
                context += f"\n\n{it+1} - {metadata['text']}\n\n"
            else:
                continue

        return context

    def run_stream(
        self,
        message,
        generation_config: GenerationConfig,
        filters={},
        search_limit=25,
        rerank_limit=15,
        *args,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Run the RAG pipeline in streaming mode.
        """
        search_limit = rerank_limit
        rerank_limit = 2 * rerank_limit
        return super().run_stream(
            message=message,
            generation_config=generation_config,
            filters=filters,
            search_limit=search_limit,
            rerank_limit=rerank_limit,
        )
