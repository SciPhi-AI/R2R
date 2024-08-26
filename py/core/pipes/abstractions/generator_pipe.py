from abc import abstractmethod
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    CompletionProvider,
    PipeType,
    PromptProvider,
    RunLoggingSingleton,
)
from core.base.abstractions.llm import GenerationConfig
from core.base.pipes.base_pipe import AsyncPipe


class GeneratorPipe(AsyncPipe):
    class Config(AsyncPipe.PipeConfig):
        name: str
        task_prompt: str
        system_prompt: str = "default_system"

    def __init__(
        self,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        type: PipeType = PipeType.GENERATOR,
        config: Optional[Config] = None,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            type=type,
            config=config or self.Config(),
            pipe_logger=pipe_logger,
            *args,
            **kwargs,
        )
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider

    @abstractmethod
    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        rag_generation_config: GenerationConfig,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        pass
