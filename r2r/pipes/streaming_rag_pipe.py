import json
import logging
import uuid
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
from .search_rag_pipe import R2RSearchRAGPipe

logger = logging.getLogger(__name__)


class R2RStreamingSearchRAGPipe(R2RSearchRAGPipe):
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
        input: R2RSearchRAGPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        rag_generation_config: GenerationConfig,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        iteration = 0
        context = ""
        # dump the search results and construct the context
        yield f"<{self.SEARCH_STREAM_MARKER}>"
        for result in input.raw_search_results:
            if iteration >= 1:
                yield ","
            yield json.dumps(result.json())
            context += f"Result {iteration+1}:\n{result.metadata['text']}\n\n"
            iteration += 1
        yield f"</{self.SEARCH_STREAM_MARKER}>"

        messages = self._get_message_payload(str(input.query), context)
        yield f"<{self.COMPLETION_STREAM_MARKER}>"
        response = ""
        for chunk in self.llm_provider.get_completion_stream(
            messages=messages, generation_config=rag_generation_config
        ):
            chunk = R2RStreamingSearchRAGPipe._process_chunk(chunk)
            response += chunk
            yield chunk

        yield f"</{self.COMPLETION_STREAM_MARKER}>"

        await self.enqueue_log(
            run_id=run_id,
            key="llm_response",
            value=response,
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
