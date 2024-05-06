"""
Abstract base class for completion pipe.
"""

import json
import logging
import uuid
from abc import abstractmethod
from typing import Any, Generator, Optional, Union

from ..abstractions.output import LLMChatCompletion, RAGPipeOutput
from ..abstractions.search import SearchResult
from ..providers.embedding import EmbeddingProvider
from ..providers.llm import GenerationConfig, LLMProvider
from ..providers.prompt import PromptProvider
from ..providers.vector_db import VectorDBProvider
from ..utils.logging import LoggingDatabaseConnection, log_output_to_db
from .pipe import Pipe

logger = logging.getLogger(__name__)


class RAGPipe(Pipe):
    SEARCH_STREAM_MARKER = "search"
    CONTEXT_STREAM_MARKER = "context"
    METADATA_STREAM_MARKER = "metadata"
    COMPLETION_STREAM_MARKER = "completion"

    def __init__(
        self,
        prompt_provider: PromptProvider,
        embedding_provider: EmbeddingProvider,
        llm_provider: LLMProvider,
        vector_db_provider: VectorDBProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.prompt_provider = prompt_provider
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider
        self.vector_db_provider = vector_db_provider
        self.pipe_run_info = None

        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipe(
        self, message: str, search_only: bool, *args, **kwargs
    ) -> None:
        self.pipe_run_info = {
            "run_id": uuid.uuid4(),
            "type": "rag" if not search_only else "search",
        }
        self.ingress(message)

    @log_output_to_db
    def ingress(self, message: str) -> Any:
        """
        Ingresses data into the pipe.
        """
        return message

    @log_output_to_db
    def transform_message(
        self,
        message: str,
        generation_config: Optional[GenerationConfig] = None,
    ) -> Any:
        """
        Transforms the input query before retrieval, if necessary.
        """
        return message

    @log_output_to_db
    def search(
        self,
        query: str,
        filters: dict,
        limit: int,
        *args,
        **kwargs,
    ) -> list[SearchResult]:
        """
        Searches the vector database with the transformed query to retrieve relevant documents.
        """
        logger.debug(f"Retrieving results for query: {query}")
        results = self.vector_db_provider.search(
            query_vector=self.embedding_provider.get_embedding(
                query,
            ),
            filters=filters,
            limit=limit,
        )

        logger.debug(f"Retrieved the raw results shown:\n{results}\n")

        return results

    def rerank_results(
        self,
        query: str,
        results: list[SearchResult],
        limit: int,
    ) -> list[SearchResult]:
        """
        Reranks the retrieved documents based on relevance, if necessary.
        """
        return self.embedding_provider.rerank(query, results, limit=limit)

    def _format_results(self, results: list[SearchResult]) -> str:
        """
        Formats the reranked results into a human-readable string.
        """
        context = ""
        for it, ele in enumerate(results):
            metadata = ele.metadata
            context += f"\n\n{it+1} - {metadata['text']}\n\n"
        return context

    @log_output_to_db
    def construct_context(
        self,
        results: list[SearchResult],
        *args,
        **kwargs,
    ) -> str:
        return self._format_results(results)

    @log_output_to_db
    def construct_prompt(self, inputs: dict[str, str]) -> str:
        """
        Constructs a prompt for generation based on the reranked chunks.
        """
        return self.prompt_provider.get_prompt("return_pompt", inputs).format(
            **inputs
        )

    @log_output_to_db
    def generate_completion(
        self,
        prompt: str,
        generation_config: GenerationConfig,
        conversation: list[dict] = None,
    ) -> Union[Generator[str, None, None], LLMChatCompletion]:
        """
        Generates a completion based on the prompt.
        """
        if not conversation:
            messages = [
                {
                    "role": "system",
                    "content": self.prompt_provider.get_prompt(
                        "system_prompt"
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ]
        else:
            messages = [
                *conversation,
                {
                    "role": "user",
                    "content": prompt,
                },
            ]

        if not generation_config.stream:
            return self.llm_provider.get_completion(
                messages, generation_config
            )

        return self._stream_generate_completion(messages, generation_config)

    def _stream_generate_completion(
        self, messages: list[dict], generation_config: GenerationConfig
    ) -> Generator[str, None, None]:
        for result in self.llm_provider.get_completion_stream(
            messages, generation_config
        ):
            yield result.choices[0].delta.content or ""  # type: ignore

    def run(
        self,
        message: str,
        filters: dict[str, str] = {},
        search_limit: int = 25,
        rerank_limit: int = 15,
        search_only: bool = False,
        generation_config: Optional[GenerationConfig] = None,
        *args,
        **kwargs,
    ) -> Union[RAGPipeOutput, LLMChatCompletion]:
        """
        Runs the completion pipe for non-streaming execution.
        """
        if generation_config and generation_config.stream:
            raise ValueError(
                "Streaming mode must be enabled when running `run_stream`."
            )
        self.initialize_pipe(message, search_only)

        query = self.transform_message(message, generation_config)
        search_results = self.search(query, filters, search_limit)
        search_results = self.rerank_results(
            query, search_results, rerank_limit
        )

        if search_only:
            return RAGPipeOutput(search_results, None, None)
        if not generation_config:
            raise ValueError(
                "GenerationConfig is required for completion generation."
            )

        context = self.construct_context(search_results)
        prompt = self.construct_prompt({"query": query, "context": context})

        completion = self.generate_completion(prompt, generation_config)
        return RAGPipeOutput(search_results, context, completion)

    def run_stream(
        self,
        message: str,
        generation_config: GenerationConfig,
        filters={},
        search_limit=25,
        rerank_limit=15,
        *args,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Runs the completion pipe for streaming execution.
        """
        if not generation_config.stream:
            raise ValueError(
                "Streaming mode must be enabled when running `run_stream."
            )

        self.initialize_pipe(message, search_only=False)

        query = self.transform_message(message, generation_config)
        search_results = self.search(query, filters, search_limit)
        search_results = self.rerank_results(
            query, search_results, rerank_limit
        )

        context = self.construct_context(search_results)
        prompt = self.construct_prompt({"query": query, "context": context})

        return self._return_stream(
            search_results, context, prompt, generation_config
        )

    def _return_stream(
        self,
        search_results: list[SearchResult],
        context: str,
        prompt: str,
        generation_config: GenerationConfig,
        metadata: Optional[dict] = None,
    ) -> Generator[str, None, None]:
        yield f"<{RAGPipe.SEARCH_STREAM_MARKER}>"
        yield json.dumps([ele.dict() for ele in search_results])
        yield f"</{RAGPipe.SEARCH_STREAM_MARKER}>"

        yield f"<{RAGPipe.CONTEXT_STREAM_MARKER}>"
        yield context
        yield f"</{RAGPipe.CONTEXT_STREAM_MARKER}>"

        yield f"<{RAGPipe.METADATA_STREAM_MARKER}>"
        yield json.dumps(metadata or {})
        yield f"</{RAGPipe.METADATA_STREAM_MARKER}>"

        yield f"<{RAGPipe.COMPLETION_STREAM_MARKER}>"
        for chunk in self.generate_completion(prompt, generation_config):
            yield chunk
        yield f"</{RAGPipe.COMPLETION_STREAM_MARKER}>"

    def _get_extra_args(self, *args, **kwargs):
        """
        Retrieves any extra arguments needed for the pipe's operations.
        """
        return {}
