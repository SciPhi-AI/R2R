from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional

from r2r.core import (
    AsyncPipe,
    AsyncState,
    GenerationConfig,
    LLMProvider,
    PipeType,
    PromptProvider,
)


class GeneratorPipe(AsyncPipe):
    class Config(AsyncPipe.PipeConfig):
        name: str
        task_prompt: str
        generation_config: GenerationConfig
        system_prompt: str = "default_system_prompt"

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        type: PipeType = PipeType.GENERATOR,
        config: Optional[Config] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            type=type,
            config=config or self.Config(),
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
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        pass

    @abstractmethod
    def _get_llm_payload(
        self, message: str, *args: Any, **kwargs: Any
    ) -> list:
        pass
