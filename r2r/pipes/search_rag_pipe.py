import logging
import uuid
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

from .abstractions.generator_pipe import GeneratorPipe

logger = logging.getLogger(__name__)


class R2RSearchRAGPipe(GeneratorPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[SearchResult, None]
        query: list[str]
        raw_search_results: Optional[list[SearchResult]] = None
        dummy: Optional[str] = None

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        type: PipeType = PipeType.GENERATOR,
        config: Optional[GeneratorPipe] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            llm_provider=llm_provider,
            prompt_provider=prompt_provider,
            type=type,
            config=config
            or GeneratorPipe.Config(
                name="default_rag_pipe", task_prompt="default_rag"
            ),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self,
        input: Input,
        state: AsyncState,
        run_id: uuid.UUID,
        rag_generation_config: GenerationConfig,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[LLMChatCompletion, None]:
        context = await self._collect_context(input)
        messages = self._get_message_payload("\n".join(input.query), context)

        response = self.llm_provider.get_completion(
            messages=messages, generation_config=rag_generation_config
        )
        yield response

        await self.enqueue_log(
            run_id=run_id,
            key="llm_response",
            value=response.choices[0].message.content,
        )

    def _get_message_payload(self, query: str, context: str) -> dict:
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

    async def _collect_context(self, input: Input) -> str:
        iteration = 0
        context = ""
        async for result in input.message:
            context += f"Result {iteration+1}:\n{result.metadata['text']}\n\n"
            iteration += 1

        return context
