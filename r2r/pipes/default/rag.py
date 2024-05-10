import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import (
    AsyncPipe,
    AsyncState,
    GenerationConfig,
    LLMChatCompletion,
    LLMProvider,
    PipeFlow,
    PipeType,
    PromptProvider,
)

from ..abstractions.generator import GeneratorPipe

logger = logging.getLogger(__name__)


class DefaultRAGPipe(GeneratorPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[str, None]
        context: str

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        flow: PipeFlow = PipeFlow.STANDARD,
        type: PipeType = PipeType.GENERATOR,
        config: Optional[GeneratorPipe] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            llm_provider=llm_provider,
            prompt_provider=prompt_provider,
            flow=flow,
            type=type,
            config=config
            or GeneratorPipe.Config(
                name="default_rag_pipe",
                task_prompt="default_rag_prompt",
                generation_config=GenerationConfig(model="gpt-3.5-turbo"),
            ),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
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
