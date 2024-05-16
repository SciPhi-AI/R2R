import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import (
    AsyncPipe,
    AsyncState,
    GenerationConfig,
    LLMChatCompletion,
    LLMProvider,
    PipeType,
    PromptProvider,
    SearchResult,
)

from ..abstractions.generator import GeneratorPipe

logger = logging.getLogger(__name__)


class DefaultRAGPipe(GeneratorPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[SearchResult, None] # context
        query: list[str]
        raw_search_results: Optional[list[SearchResult]] = None
        dummy: Optional[str] = None

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        type: PipeType = PipeType.GENERATOR,
        config: Optional[GeneratorPipe] = None,
        generation_config: Optional[GenerationConfig] = None,
        *args,
        **kwargs,
    ):
        if config and generation_config:
            raise ValueError(
                "Cannot provide both `config` and `generation_config`."
            )
        super().__init__(
            llm_provider=llm_provider,
            prompt_provider=prompt_provider,
            type=type,
            config=config
            or GeneratorPipe.Config(
                name="default_rag_pipe",
                task_prompt="default_rag_prompt",
                generation_config=generation_config
                or GenerationConfig(model="gpt-3.5-turbo"),
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
        config_override = kwargs.get("config_override", None)
        async for context in input.message:
            messages = self._get_llm_payload("\n".join(input.query), context)
            response = self.llm_provider.get_completion(
                messages=messages,
                generation_config=config_override
                or self.config.generation_config,
            )
            yield response

            await self.enqueue_log(
                pipe_run_id=self.run_info.run_id,
                key="response",
                value=response,
            )

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
                        "query": "\n".join(query),
                        "context": context,
                    },
                ),
            },
        ]
