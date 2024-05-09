import logging
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

from r2r.core import (
    AsyncContext,
    AsyncPipe,
    GenerationConfig,
    LLMProvider,
    PipeConfig,
    PipeFlow,
    PipeType,
    PromptProvider,
)

from ..abstractions.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class DefaultQueryTransformPipe(LoggableAsyncPipe):
    class QueryTransformConfig(BaseModel, PipeConfig):
        name: str = "default_query_transform"
        num_answers: int = 3
        model: str = "gpt-3.5-turbo"
        system_prompt: str = "default_system_prompt"
        task_prompt: str = "hyde_prompt"
        generation_config: GenerationConfig = GenerationConfig(
            model="gpt-3.5-turbo"
        )

        class Config:
            extra = "forbid"

    """
    Stores embeddings in a vector database asynchronously.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        config: Optional[QueryTransformConfig] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the async vector storage pipe with necessary components and configurations.
        """
        logger.info(
            f"Initalizing an `DefaultQueryTransformPipe` to store embeddings in a vector database."
        )
        if config and not isinstance(
            config, DefaultQueryTransformPipe.QueryTransformConfig
        ):
            raise ValueError(
                "Invalid configuration provided for `DefaultQueryTransformPipe`."
            )

        super().__init__(
            config=config or DefaultQueryTransformPipe.QueryTransformConfig(),
            *args,
            **kwargs,
        )
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider

    @property
    def type(self) -> PipeType:
        return PipeType.QUERY_TRANSFORM

    @property
    def flow(self) -> PipeFlow:
        return PipeFlow.FAN_OUT

    def input_from_dict(self, input_dict: dict) -> AsyncPipe.Input:
        return AsyncPipe.Input(**input_dict)

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        context: AsyncContext,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        yield None
        # async def yielder():
        #     for aentry in ["a", "b", "c"]:
        #         yield aentry

        # async for query in yielder():
        #     yield query
        # await self._initialize_pipe(input, context)

        # messages = self._get_llm_payload(input.message)

        # response = self.llm_provider.get_completion(
        #     messages=messages,
        #     generation_config=self.config.generation_config,
        # )
        # content = self.llm_provider.extract_content(response)
        # queries = content.split("\n\n")

        # await context.update(
        #     self.config.name, {"output": {"queries": queries}}
        # )

        # for query in queries:
        #     yield query

    def _get_llm_payload(self, input: str) -> dict:
        return [
            {
                "role": "system",
                "content": self.prompt_provider.get_prompt(
                    self.config.system_prompt,
                ),
            },
            {
                "role": "user",
                "content": self.prompt_provider.get_prompt(
                    self.config.task_prompt,
                    inputs={
                        "message": input,
                        "num_answers": self.config.num_answers,
                    },
                ),
            },
        ]
