import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Generator, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    CompletionProvider,
    LLMChatCompletionChunk,
    PipeType,
    PromptProvider,
    format_search_results_for_llm,
    format_search_results_for_stream,
)
from core.base.abstractions import GenerationConfig

from ..abstractions.generator_pipe import GeneratorPipe

logger = logging.getLogger()


class StreamingSearchRAGPipe(GeneratorPipe):
    VECTOR_SEARCH_STREAM_MARKER = (
        "search"  # TODO - change this to vector_search in next major release
    )
    KG_LOCAL_SEARCH_STREAM_MARKER = "kg_local_search"
    KG_GLOBAL_SEARCH_STREAM_MARKER = "kg_global_search"
    COMPLETION_STREAM_MARKER = "completion"

    def __init__(
        self,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        config: GeneratorPipe.PipeConfig,
        type: PipeType = PipeType.GENERATOR,
        *args,
        **kwargs,
    ):
        super().__init__(
            llm_provider,
            prompt_provider,
            config,
            type,
            *args,
            **kwargs,
        )
        self._config: GeneratorPipe.PipeConfig

    @property
    def config(self) -> GeneratorPipe.PipeConfig:
        return self._config

    async def _run_logic(  # type: ignore
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: UUID,
        rag_generation_config: GenerationConfig,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        context = ""
        async for query, search_results in input.message:
            result = format_search_results_for_stream(search_results)
            yield result
            gen_context = format_search_results_for_llm(search_results)
            context += gen_context

        messages = await self.prompt_provider._get_message_payload(
            system_prompt_name=self.config.system_prompt,
            task_prompt_name=self.config.task_prompt,
            task_inputs={"query": query, "context": context},
        )
        yield f"<{self.COMPLETION_STREAM_MARKER}>"
        response = ""
        for chunk in self.llm_provider.get_completion_stream(
            messages=messages, generation_config=rag_generation_config
        ):
            chunk_txt = StreamingSearchRAGPipe._process_chunk(chunk)
            response += chunk_txt
            yield chunk_txt

        yield f"</{self.COMPLETION_STREAM_MARKER}>"

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

    @staticmethod
    def _process_chunk(chunk: LLMChatCompletionChunk) -> str:
        return chunk.choices[0].delta.content or ""
