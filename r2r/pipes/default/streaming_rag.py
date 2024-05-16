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

from ..abstractions.generator import GeneratorPipe
from .rag import DefaultRAGPipe

logger = logging.getLogger(__name__)


class DefaultStreamingRAGPipe(DefaultRAGPipe):
    SEARCH_STREAM_MARKER = "search"
    COMPLETION_STREAM_MARKER = "completion"

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
                name="default_streaming_rag_pipe",
                task_prompt="default_rag_prompt",
                generation_config=generation_config
                or GenerationConfig(model="gpt-3.5-turbo", stream=True),
            ),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self,
        input: DefaultRAGPipe.Input,
        state: AsyncState,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        config_override = kwargs.get("config_override", None)
        response = ""

        async for context in input.message:
            messages = self._get_llm_payload(input.query, context)

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
                        generation_config=config_override
                        or self.config.generation_config,
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

    def _get_llm_payload(
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


import logging
from typing import Any, AsyncGenerator, Generator, Optional

from r2r.core import (
    AsyncPipe,
    AsyncState,
    GenerationConfig,
    LLMChatCompletion,
    LLMChatCompletionChunk,
    LLMProvider,
    PipeType,
    PromptProvider,
)

from ..abstractions.generator import GeneratorPipe
from .rag import DefaultRAGPipe

logger = logging.getLogger(__name__)


class DefaultStreamingRAGPipe(DefaultRAGPipe):
    SEARCH_STREAM_MARKER = "search"
    COMPLETION_STREAM_MARKER = "completion"

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
                name="default_streaming_rag_pipe",
                task_prompt="default_rag_prompt",
                generation_config=generation_config
                or GenerationConfig(model="gpt-4-turbo", stream=True),
            ),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self,
        input: DefaultRAGPipe.Input,
        state: AsyncState,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        config_override = kwargs.get("config_override", None)

        iteration = 0
        context = ""
        async for result in input.message:
            context += f"Result {iteration+1}:\n{result.metadata['text']}\n\n"
            iteration += 1

        messages = self._get_llm_payload("\n".join(input.query), context)

        async for chunk in self._yield_chunks(
            f"<{self.SEARCH_STREAM_MARKER}>",
            json.dumps([result.json() for result in input.raw_search_results]),
            f"</{self.SEARCH_STREAM_MARKER}>",
        ):
            yield chunk

        async for chunk in self._yield_chunks(
            f"<{self.COMPLETION_STREAM_MARKER}>",
            (
                self._process_chunk(chunk)
                for chunk in self.llm_provider.get_completion_stream(
                    messages=messages,
                    generation_config=config_override
                    or self.config.generation_config,
                )
            ),
            f"</{self.COMPLETION_STREAM_MARKER}>",
        ):
            yield chunk

    async def _yield_chunks(
        self,
        start_marker: str,
        chunks: Generator[str, None, None],
        end_marker: str,
    ) -> AsyncGenerator[str, None]:
        yield start_marker
        for chunk in chunks:
            yield chunk
        yield end_marker

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

    @staticmethod
    def _process_chunk(chunk: LLMChatCompletionChunk) -> str:
        return chunk.choices[0].delta.content or ""
