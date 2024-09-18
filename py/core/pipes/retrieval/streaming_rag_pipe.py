import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Generator, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    CompletionProvider,
    CompletionRecord,
    LLMChatCompletionChunk,
    PipeType,
    PromptProvider,
)
from core.base.abstractions.llm import GenerationConfig

from ..abstractions.generator_pipe import GeneratorPipe
from .search_rag_pipe import SearchRAGPipe

logger = logging.getLogger(__name__)


class StreamingSearchRAGPipe(SearchRAGPipe):
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
        input: SearchRAGPipe.Input,
        state: AsyncState,
        rag_generation_config: GenerationConfig,
        completion_record: Optional[CompletionRecord] = None,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        run_id = kwargs.get("run_id")
        iteration = 0
        context = ""
        async for query, search_results in input.message:
            # Vector Search Results
            yield f"<{self.VECTOR_SEARCH_STREAM_MARKER}>"
            if search_results.vector_search_results:
                context += "Vector Search Results:\n"
                vector_results_list = []
                for result in search_results.vector_search_results:
                    vector_results_list.append(result.json())
                    context += f"{iteration + 1}:\n{result.text}\n\n"
                    iteration += 1
                yield json.dumps(vector_results_list)
            yield f"</{self.VECTOR_SEARCH_STREAM_MARKER}>"

            if search_results.kg_search_results:
                if search_results.kg_search_results[0].local_result:
                    context += "KG Local Search Results:\n"
                    yield f"<{self.KG_LOCAL_SEARCH_STREAM_MARKER}>"
                    yield json.dumps(
                        search_results.kg_search_results[0].local_result.json()
                    )
                    context += str(
                        search_results.kg_search_results[0].local_result
                    )
                    yield f"</{self.KG_LOCAL_SEARCH_STREAM_MARKER}>"

                if (
                    search_results.kg_search_results
                    and search_results.kg_search_results[0].global_result
                ):
                    context += "KG Global Search Results:\n"
                    yield f"<{self.KG_GLOBAL_SEARCH_STREAM_MARKER}>"
                    for result in search_results.kg_search_results:
                        if iteration >= 1:
                            yield ","
                        yield json.dumps(result.global_result.json())
                        context += f"{iteration + 1}:\n{result}\n\n"
                        iteration += 1
                    yield f"</{self.KG_GLOBAL_SEARCH_STREAM_MARKER}>"

            messages = self.prompt_provider._get_message_payload(
                system_prompt_name=self.config.system_prompt,
                task_prompt_name=self.config.task_prompt,
                task_inputs={"query": query, "context": context},
            )
            yield f"<{self.COMPLETION_STREAM_MARKER}>"

            response = ""
            for chunk in self.llm_provider.get_completion_stream(
                messages=messages, generation_config=rag_generation_config
            ):
                chunk = StreamingSearchRAGPipe._process_chunk(chunk)
                response += chunk
                yield chunk

            yield f"</{self.COMPLETION_STREAM_MARKER}>"

            completion_record.search_results = search_results
            completion_record.llm_response = response
            completion_record.completion_end_time = datetime.now()
            await self.log_completion_record(run_id, completion_record)

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

    @staticmethod
    def _process_chunk(chunk: LLMChatCompletionChunk) -> str:
        return chunk.choices[0].delta.content or ""

    async def log_completion_record(
        self, run_id: UUID, completion_record: CompletionRecord
    ):
        await self.enqueue_log(
            run_id=run_id,
            key="completion_record",
            value=completion_record.to_json(),
        )
