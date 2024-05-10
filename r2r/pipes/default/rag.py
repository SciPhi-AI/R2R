import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import (
    AsyncContext,
    AsyncPipe,
    LLMProvider,
    PromptProvider,
    GenerationConfig,
    LLMChatCompletion,
    PipeFlow,
    PipeType,
)

logger = logging.getLogger(__name__)


class DefaultRAGPipe(AsyncPipe):

    class Config(AsyncPipe.PipeConfig):
        name: str = "default_rag"
        system_prompt: str = "default_system_prompt"
        task_prompt: str = "default_rag_prompt"
        generation_config: GenerationConfig = GenerationConfig(
            model="gpt-3.5-turbo"
        )

    class Input(AsyncPipe.Input):
        message: AsyncGenerator[str, None]
        context: str

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        flow: PipeFlow = PipeFlow.STANDARD,
        type: PipeType = PipeType.GENERATION,
        config: Optional[Config] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            flow=flow,
            type=type,
            config=config or DefaultRAGPipe.Config(),
            *args,
            **kwargs,
        )
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider

    async def _run_logic(
        self,
        input: Input,
        context: AsyncContext,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[LLMChatCompletion, None]:
        async for query in input.message:
            messages = self._get_llm_payload(query, input.context)

            response = self.llm_provider.get_completion(
                messages=messages,
                generation_config=self.config.generation_config,
            )
            yield response

    def _get_llm_payload(self, query: str, context: str) -> dict:
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
                        "query": query,
                        "context": context,
                    },
                ),
            },
        ]
