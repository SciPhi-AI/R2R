"""
Abstract base class for completion pipelines.
"""

import json
import logging
import uuid
from abc import abstractmethod
from typing import Any, Generator, Optional, Union

from openai.types.chat import ChatCompletion

from ..abstractions.output import RAGPipelineOutput
from ..providers.llm import GenerationConfig, LLMProvider
from ..providers.logging import LoggingDatabaseConnection, log_execution_to_db
from ..providers.prompt import PromptProvider
from .pipeline import Pipeline

logger = logging.getLogger(__name__)


class RAGPipeline(Pipeline):
    SEARCH_STREAM_MARKER = "search"
    CONTEXT_STREAM_MARKER = "context"
    COMPLETION_STREAM_MARKER = "completion"

    def __init__(
        self,
        llm: "LLMProvider",
        prompt_provider: PromptProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.llm = llm
        self.prompt_provider = prompt_provider
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
        transformed_query,
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
    def rerank_results(self, results: list) -> list:
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
        reranked_results = self.rerank_results(results)
        return self._format_results(reranked_results)

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
    ) -> Union[Generator[str, None, None], ChatCompletion]:
        """
        Generates a completion based on the prompt.
        """
        self._check_pipeline_initialized()
        messages = [
            {
                "role": "system",
                "content": self.prompt_provider.get_prompt("system_prompt"),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]
        if not generation_config.stream:
            return self.llm.get_completion(messages, generation_config)

        return self._stream_generate_completion(messages, generation_config)

    def _stream_generate_completion(
        self, messages: list[dict], generation_config: GenerationConfig
    ) -> Generator[str, None, None]:
        for result in self.llm.get_completion_stream(
            messages, generation_config
        ):
            yield result.choices[0].delta.content or ""  # type: ignore

    def run(
        self,
        query,
        filters={},
        limit=10,
        search_only=False,
        generation_config: Optional[GenerationConfig] = None,
        *args,
        **kwargs,
    ) -> Union[Generator[str, None, None], RAGPipelineOutput]:
        """
        Runs the completion pipeline.
        """
        self.initialize_pipeline(query, search_only)

        transformed_query = self.transform_query(query)
        search_results = self.search(transformed_query, filters, limit)
        if search_only:
            return RAGPipelineOutput(search_results, None, None)
        elif not generation_config:
            raise ValueError(
                "GenerationConfig is required for completion generation."
            )
        elif search_only and generation_config:
            raise ValueError(
                "GenerationConfig is not required for search only."
            )

        context = self.construct_context(search_results)

        prompt = self.construct_prompt(
            {"query": transformed_query, "context": context}
        )

        if not generation_config.stream:
            completion = self.generate_completion(prompt, generation_config)
            return RAGPipelineOutput(search_results, context, completion)

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
