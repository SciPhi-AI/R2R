"""
Abstract base class for completion pipelines.
"""

import json
import logging
import uuid
from abc import abstractmethod
from typing import Any, Generator, Optional, Union


from ..abstractions.output import RAGPipelineOutput, LLMChatCompletion
from ..providers.embedding import EmbeddingProvider
from ..providers.llm import GenerationConfig, LLMProvider
from ..providers.prompt import PromptProvider
from ..providers.vector_db import VectorDBProvider
from ..utils.logging import LoggingDatabaseConnection, log_execution_to_db
from .pipeline import Pipeline

logger = logging.getLogger(__name__)


class RAGPipeline(Pipeline):
    SEARCH_STREAM_MARKER = "search"
    CONTEXT_STREAM_MARKER = "context"
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

        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipeline(
        self, query: str, search_only: bool, *args, **kwargs
    ) -> None:
        self.pipeline_run_info = {
            "run_id": uuid.uuid4(),
            "type": "rag" if not search_only else "search",
        }
        self.ingress(query)

    @log_execution_to_db
    def ingress(self, data: Any) -> Any:
        """
        Ingresses data into the pipeline.
        """
        self._check_pipeline_initialized()
        return data

    @abstractmethod
    def transform_query(self, query: str) -> Any:
        """
        Transforms the input query for retrieval.
        """
        pass

    @abstractmethod
    def search(
        self,
        transformed_query: Any,
        filters: dict[str, Any],
        limit: int,
        *args,
        **kwargs,
    ) -> list:
        """
        Retrieves results based on the transformed query.
        The search_type parameter allows for specifying the type of search,
        """
        pass

    @abstractmethod
    def rerank_results(
        self, transformed_query: Any, results: list, limit: int
    ) -> list:
        """
        Reranks the retrieved results based on relevance or other criteria.
        """
        pass

    @abstractmethod
    def _format_results(self, results: list) -> str:
        """
        Formats the results for generation.
        """
        pass

    @log_execution_to_db
    def construct_context(
        self,
        results: list,
    ) -> str:
        return self._format_results(results)

    @log_execution_to_db
    def construct_prompt(self, inputs: dict[str, str]) -> str:
        """
        Constructs a prompt for generation based on the reranked chunks.
        """
        return self.prompt_provider.get_prompt("task_prompt", inputs).format(
            **inputs
        )

    @log_execution_to_db
    def generate_completion(
        self,
        prompt: str,
        generation_config: GenerationConfig,
        conversation: list[dict] = None,
    ) -> Union[Generator[str, None, None], LLMChatCompletion]:
        """
        Generates a completion based on the prompt.
        """
        self._check_pipeline_initialized()

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
        query,
        filters={},
        search_limit=25,
        rerank_limit=15,
        search_only=False,
        generation_config: Optional[GenerationConfig] = None,
        *args,
        **kwargs,
    ) -> Union[RAGPipelineOutput, ChatCompletion]:
        """
        Runs the completion pipeline for non-streaming execution.
        """
        if generation_config and generation_config.stream:
            raise ValueError(
                "Streaming mode must be enabled when running `run_stream`."
            )
        self.initialize_pipeline(query, search_only)

        transformed_query = self.transform_query(query)
        search_results = self.search(transformed_query, filters, search_limit)
        search_results = self.rerank_results(
            transformed_query, search_results, rerank_limit
        )

        if search_only:
            return RAGPipelineOutput(search_results, None, None)
        if not generation_config:
            raise ValueError(
                "GenerationConfig is required for completion generation."
            )

        context = self.construct_context(search_results)
        prompt = self.construct_prompt(
            {"query": transformed_query, "context": context}
        )

        completion = self.generate_completion(prompt, generation_config)
        return RAGPipelineOutput(search_results, context, completion)

    def run_stream(
        self,
        query,
        generation_config: GenerationConfig,
        filters={},
        search_limit=25,
        rerank_limit=15,
        *args,
        **kwargs,
    ) -> Generator[str, None, None]:
        """
        Runs the completion pipeline for streaming execution.
        """
        if not generation_config.stream:
            raise ValueError(
                "Streaming mode must be enabled when running `run_stream."
            )

        self.initialize_pipeline(query, search_only=False)

        transformed_query = self.transform_query(query)
        search_results = self.search(transformed_query, filters, search_limit)
        search_results = self.rerank_results(
            transformed_query, search_results, rerank_limit
        )

        context = self.construct_context(search_results)
        prompt = self.construct_prompt(
            {"query": transformed_query, "context": context}
        )

        return self._stream_run(
            search_results, context, prompt, generation_config
        )


    def _stream_run(
        self,
        search_results: list,
        context: str,
        prompt: str,
        generation_config: GenerationConfig,
    ) -> Generator[str, None, None]:
        yield f"<{RAGPipeline.SEARCH_STREAM_MARKER}>"
        yield json.dumps([ele.to_dict() for ele in search_results])
        yield f"</{RAGPipeline.SEARCH_STREAM_MARKER}>"

        yield f"<{RAGPipeline.CONTEXT_STREAM_MARKER}>"
        yield context
        yield f"</{RAGPipeline.CONTEXT_STREAM_MARKER}>"
        yield f"<{RAGPipeline.COMPLETION_STREAM_MARKER}>"
        for chunk in self.generate_completion(prompt, generation_config):
            yield chunk
        yield f"</{RAGPipeline.COMPLETION_STREAM_MARKER}>"

    def _get_extra_args(self, *args, **kwargs):
        """
        Retrieves any extra arguments needed for the pipeline's operations.
        """
        return {}
