"""
Abstract base class for completion pipelines.
"""
import logging
import uuid
from abc import abstractmethod
from typing import Any, Generator, Optional, Union

from ..abstractions.completion import Completion, RAGCompletion
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
        *args,
        **kwargs,
    ):
        self.llm = llm
        self.generation_config = generation_config
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.task_prompt = task_prompt or DEFAULT_TASK_PROMPT
        self.logging_provider = logging_provider
        self.pipeline_run_info = None
        super().__init__(logging_provider=logging_provider, **kwargs)

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
        return self.task_prompt.format(**inputs)

    @log_execution_to_db
    def generate_completion(
        self,
        prompt: str,
        generate_with_chat=True,
        stream: bool = False,
    ) -> Completion:
        """
        Generates a completion based on the prompt.
        """
        self._check_pipeline_initialized()
        print('passing stream = ', stream)

        if generate_with_chat:
            if stream:
                print("trying to yield results...")
                for result in self.llm.get_chat_completion(
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
                    stream=True,
                ):
                    yield result
            else:
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
                    stream=False,
                )
        else:
            raise NotImplementedError(
                "Generation without chat is not implemented yet."
            )

    def run(
        self, query, filters={}, limit=10, search_only=False, stream=False
    ) -> Union[Generator[str, None, None], RAGCompletion]:
        """
        Runs the completion pipeline.
        """
        print("in the run....")
        self.initialize_pipeline(query, search_only)

        logger.debug(f"Pipeline run type: {self.pipeline_run_info}")

        transformed_query = self.transform_query(query)
        search_results = self.search(transformed_query, filters, limit)
        if search_only:
            if stream:
                raise ValueError("Streaming is not supported for search only.")
            return RAGCompletion(search_results, None, None)
        
        print("search_results = ", search_results)
        context = self.construct_context(search_results)
        prompt = self.construct_prompt(
            {"query": transformed_query, "context": context}
        )
        print("are we streaming...?")

        if stream:
            yield "<SEARCH_RESULTS>"
            yield "[" + str(
                ",".join([str(ele.to_dict()) for ele in search_results])
            ) + "]"
            yield "</SEARCH_RESULTS>"

            print("context = ", context)
            yield "<CONTEXT>"
            yield context
            yield "</CONTEXT>"
            print("attempting to stream response...")
            yield "<RESPONSE>"
            for chunk in self.generate_completion(
                prompt, stream=True
            ):
                print("chunk = ", chunk)
                yield chunk
            yield "<RESPONSE>"
        else:
            completion = self.generate_completion(
                prompt, stream=False
            )
            return RAGCompletion(search_results, context, completion)

    def _get_extra_args(self,  *args, **kwargs):
        """
        Retrieves any extra arguments needed for the pipeline's operations.
        """
        return {}
