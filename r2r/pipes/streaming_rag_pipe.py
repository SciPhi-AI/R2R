import json
import logging
from typing import Any, AsyncGenerator, Generator, Optional

from r2r.core import (
    AsyncState,
    GenerationConfig,
    LLMChatCompletionChunk,
    LLMProvider,
    PipeType,
    PromptProvider,
)

from .abstractions.generator_pipe import GeneratorPipe
from .rag_pipe import R2RRAGPipe

logger = logging.getLogger(__name__)


class R2RStreamingRAGPipe(R2RRAGPipe):
    SEARCH_STREAM_MARKER = "search"
    COMPLETION_STREAM_MARKER = "completion"

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
                name="default_streaming_rag_pipe", task_prompt="default_rag"
            ),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self,
        input: R2RRAGPipe.Input,
        state: AsyncState,
        rag_generation_config: GenerationConfig,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        response = ""

        async for context in input.message:
            messages = self._get_message_payload(input.query, context)

            response += await self._yield_chunks(
                f"<{self.SEARCH_STREAM_MARKER}>",
                (
                    f'"{json.dumps(result.dict())}",'
                    for result in input.raw_search_results
                ),
                f"</{self.SEARCH_STREAM_MARKER}>",
            )
            response += await self._yield_chunks(
                f"<{self.COMPLETION_STREAM_MARKER}>",
                (
                    self._process_chunk(chunk)
                    for chunk in self.llm_provider.get_completion_stream(
                        messages=messages,
                        generation_config=rag_generation_config,
                    )
                ),
                f"</{self.COMPLETION_STREAM_MARKER}>",
            )

    async def _yield_chunks(
        self,
        start_marker: str,
        chunks: Generator[str, None, None],
        end_marker: str,
    ) -> str:
        yield start_marker
        for chunk in chunks:
            yield chunk
        yield end_marker

    def _get_message_payload(
        self, query: str, context: str
    ) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": self.prompt_provider.get_prompt(
                    self.config.system_prompt
                ),
            },
            {
                "role": "user",
                "content": self.prompt_provider.get_prompt(
                    self.config.task_prompt,
                    inputs={"query": query, "context": context},
                ),
            },
        ]

    @staticmethod
    def _process_chunk(chunk: LLMChatCompletionChunk) -> str:
        return chunk.choices[0].delta.content or ""
