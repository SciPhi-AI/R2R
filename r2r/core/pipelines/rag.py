"""
Abstract base class for completion pipelines.
"""
import logging
import uuid
from abc import abstractmethod
from typing import Any, Optional, Union

from openai.types import Completion
from openai.types.chat import ChatCompletion

from ..providers.llm import GenerationConfig, LLMProvider
from ..providers.logging import LoggingDatabaseConnection, log_execution_to_db
from .pipeline import Pipeline

logger = logging.getLogger(__name__)

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


class RAGPipeline(Pipeline):
    def __init__(
        self,
        llm: "LLMProvider",
        generation_config: "GenerationConfig",
        system_prompt: Optional[str] = None,
        task_prompt: Optional[str] = None,
        logging_provider: Optional[LoggingDatabaseConnection] = None,
        **kwargs,
    ):
        self.llm = llm
        self.generation_config = generation_config
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.task_prompt = task_prompt or DEFAULT_TASK_PROMPT
        self.logging_provider = logging_provider
        self.pipeline_run_info = None
        super().__init__(logging_provider=logging_provider, **kwargs)

    def initialize_pipeline(self, query: str, search_only: bool) -> None:
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
    def _get_extra_args(self, *args, **kwargs) -> dict[str, Any]:
        """
        Returns extra arguments for the generation request.
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
        return self.task_prompt.format(**inputs)

    @log_execution_to_db
    def generate_completion(
        self,
        prompt: str,
        generate_with_chat=True,
    ) -> Union[ChatCompletion, Completion]:
        """
        Generates a completion based on the prompt.
        """
        self._check_pipeline_initialized()
        if generate_with_chat:
            return self.llm.get_chat_completion(
                [
                    {
                        "role": "system",
                        "content": self.system_prompt,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                self.generation_config,
                **self._get_extra_args(),
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
        self.initialize_pipeline(query, search_only)

        logger.debug(f"Pipeline run type: {self.pipeline_run_info}")

        transformed_query = self.transform_query(query)
        search_results = self.search(transformed_query, filters, limit)
        if search_only:
            logger.debug(f"Pipeline run type: {self.pipeline_run_info}")
            return search_results

        context = self.construct_context(search_results)
        prompt = self.construct_prompt(
            {"query": transformed_query, "context": context}
        )
        return self.generate_completion(prompt, generate_with_chat=True)
