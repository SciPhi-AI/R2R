import logging
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

from r2r.core import (
    GenerationConfig,
    LLMChatCompletion,
    LLMProvider,
    LoggingDatabaseConnectionSingleton,
    PipeConfig,
    PipeFlow,
    PipeType,
    PromptProvider,
)

from ..abstractions.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class LLMGenerationConfig(BaseModel, PipeConfig):
    name: str = "default_llm_generation"
    system_prompt: str = "default_system_prompt"
    rag_prompt: str = "default_rag_prompt"


class DefaultLLMGenerationPipe(LoggableAsyncPipe):
    """
    Stores embeddings in a vector database asynchronously.
    """

    INPUT_TYPE = str
    OUTPUT_TYPE = AsyncGenerator[LLMChatCompletion, None]
    FLOW = PipeFlow.FAN_IN
    CONFIG = LLMGenerationConfig

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        config: Optional[LLMGenerationConfig] = None,
        logging_connection: Optional[
            LoggingDatabaseConnectionSingleton
        ] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the async vector storage pipe with necessary components and configurations.
        """
        logger.info(f"Initalizing an `DefaultLLMGenerationPipe` pipe.")
        if config and not isinstance(config, LLMGenerationConfig):
            raise ValueError(
                "Invalid configuration provided for `DefaultLLMGenerationPipe`."
            )
        super().__init__(
            config=config or LLMGenerationConfig(),
            logging_connection=logging_connection,
            *args,
            **kwargs,
        )
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider

    @property
    def type(self) -> PipeType:
        return PipeType.GENERATOR

    async def run(
        self,
        input: str,
        *args: Any,
        **kwargs: Any,
    ) -> OUTPUT_TYPE:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        self._initialize_pipe(input.settings)
        messages = self._get_llm_payload(input)

        return self.llm_provider.get_completion(
            messages=messages,
            generation_config=GenerationConfig(model=self.config.model),
        )

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
                    self.config.rag_prompt,
                    inputs={
                        "query": input.message,
                        "context": input.context,
                    },
                ),
            },
        ]
