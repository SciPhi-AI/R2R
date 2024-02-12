"""
Abstract base class for completion pipelines.
"""
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional, Union

from openai.types import Completion
from openai.types.chat import ChatCompletion

from ..providers.llm import GenerationConfig, LLMProvider
from .logging import LoggingDatabaseConnection, log_execution_to_db

logger = logging.getLogger("sciphi_r2r")

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."
DEFAULT_TASK_PROMPT = """
## Task:
Answer the query given immediately below given the context which follows later.

### Query:
{query}

### Context:
{context}

### Query:
{query}

## Response:
"""


class RAGPipeline(ABC):
    def __init__(
        self,
        llm: "LLMProvider",
        generation_config: "GenerationConfig",
        system_prompt: Optional[str] = None,
        task_prompt: Optional[str] = None,
        logging_database: Optional[LoggingDatabaseConnection] = None,
        **kwargs
    ):
        self.llm = llm
        self.generation_config = generation_config
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.task_prompt = task_prompt or DEFAULT_TASK_PROMPT
        self.logging_database = logging_database

        if logging_database is not None:
            self.conn = logging_database.__enter__()
            self.log_table_name = logging_database.log_table_name
        else:
            self.conn = None
            self.log_table_name = None

    def close(self):
        if self.logging_database:
            self.logging_database.__exit__(None, None, None)

    @abstractmethod
    def transform_query(self, query: str) -> Any:
        """
        Transforms the input query for retrieval.
        """
        pass

    @abstractmethod
    def retrieve_chunks(
        self,
        transformed_query,
        filters: dict[str, Any],
        limit: int,
        search_type="semantic",
    ) -> list:
        """
        Retrieves chunks based on the transformed query.
        The search_type parameter allows for specifying the type of search,
        e.g., 'semantic' or 'keyword'. Currently, only 'semantic' search is implemented.
        """
        pass

    @abstractmethod
    def rerank_chunks(self, chunks: list) -> list:
        """
        Reranks the retrieved chunks based on relevance or other criteria.
        """
        pass

    @abstractmethod
    def _get_extra_args(self, query: str, context) -> dict[str, Any]:
        """
        Returns extra arguments for the generation request.
        """
        pass

    @abstractmethod
    def _format_chunks(self, chunks: list) -> str:
        """
        Formats the chunks for generation.
        """
        pass

    @log_execution_to_db
    def construct_context(
        self,
        chunks: list,
    ) -> str:
        return self._format_chunks(chunks)

    @log_execution_to_db
    def construct_prompt(self, prompt_query: str, context: str) -> str:
        """
        Constructs a prompt for generation based on the reranked chunks.
        """
        return self.task_prompt.format(query=prompt_query, context=context)

    @log_execution_to_db
    def generate_completion(
        self,
        prompt_query: str,
        context_query: str,
        context: str,
        generate_with_chat=True,
    ) -> Union[ChatCompletion, Completion]:
        """
        Generates a completion based on the prompt.
        """
        if generate_with_chat:
            return self.llm.get_chat_completion(
                [
                    {
                        "role": "system",
                        "content": self.system_prompt,
                        "role": "user",
                        "content": prompt_query,
                    }
                ],
                self.generation_config,
                **self._get_extra_args(context_query, context),
            )
        else:
            raise NotImplementedError(
                "Generation without chat is not implemented yet."
            )

    def run(
        self, query, filters={}, limit=10, search_only=False
    ) -> Union[ChatCompletion, Completion, list]:
        """
        Runs the completion pipeline.
        """
        self.pipeline_run_id = uuid.uuid4()
        transformed_query = self.transform_query(query)
        search_results = self.retrieve_chunks(
            transformed_query, filters, limit
        )
        if search_only:
            return search_results
        context = self.construct_context(search_results)
        prompt = self.construct_prompt(transformed_query, context)
        completion = self.generate_completion(prompt, transformed_query, context)
        return completion
