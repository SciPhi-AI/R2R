from typing import Any, AsyncGenerator, Optional, Tuple
from uuid import UUID

from core.base import (
    AggregateSearchResult,
    AsyncPipe,
    AsyncState,
    CompletionProvider,
    DatabaseProvider,
    KGSearchResultType,
)
from core.base.abstractions import GenerationConfig, RAGCompletion

from ..abstractions.generator_pipe import GeneratorPipe


class SearchRAGPipe(GeneratorPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[Tuple[str, AggregateSearchResult], None]

    def __init__(
        self,
        llm_provider: CompletionProvider,
        database_provider: DatabaseProvider,
        config: GeneratorPipe.PipeConfig,
        *args,
        **kwargs,
    ):
        super().__init__(
            llm_provider,
            database_provider,
            config,
            *args,
            **kwargs,
        )
        self._config: GeneratorPipe.PipeConfig = config

    @property
    def config(self) -> GeneratorPipe.PipeConfig:  # for type hiting
        return self._config

    async def _run_logic(  # type: ignore
        self,
        input: Input,
        state: AsyncState,
        run_id: UUID,
        rag_generation_config: GenerationConfig,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[RAGCompletion, None]:
        context = ""
        search_iteration = 1
        total_results = 0
        sel_query = None
        async for query, search_results in input.message:
            if search_iteration == 1:
                sel_query = query
            context_piece, total_results = await self._collect_context(
                query, search_results, search_iteration, total_results
            )
            context += context_piece
            search_iteration += 1
        messages = (
            await self.database_provider.prompt_handler.get_message_payload(
                system_prompt_name=self.config.system_prompt,
                task_prompt_name=self.config.task_prompt,
                task_inputs={"query": sel_query, "context": context},
                task_prompt_override=kwargs.get("task_prompt_override", None),
            )
        )
        response = await self.llm_provider.aget_completion(
            messages=messages, generation_config=rag_generation_config
        )
        yield RAGCompletion(completion=response, search_results=search_results)

        if run_id:
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Response content is empty")
            await self.enqueue_log(
                run_id=run_id,
                key="llm_response",
                value=content,
            )

    async def _collect_context(
        self,
        query: str,
        results: AggregateSearchResult,
        iteration: int,
        total_results: int,
    ) -> Tuple[str, int]:
        context = f"Query:\n{query}\n\n"
        if results.chunk_search_results:
            context += f"Vector Search Results({iteration}):\n"
            it = total_results + 1
            for result in results.chunk_search_results:
                context += f"[{it}]: {result.text}\n\n"
                it += 1
            total_results = (
                it - 1
            )  # Update total_results based on the last index used
        if results.graph_search_results:
            context += f"Knowledge Graph ({iteration}):\n"
            it = total_results + 1
            for search_result in results.graph_search_results:  # [1]:
                # if associated_query := search_results.metadata.get(
                #     "associated_query"
                # ):
                #     context += f"Query: {associated_query}\n\n"
                # context += f"Results:\n"
                if search_result.result_type == KGSearchResultType.ENTITY:
                    context += f"[{it}]: Entity Name - {search_result.content.name}\n\nDescription - {search_result.content.description}\n\n"
                elif (
                    search_result.result_type
                    == KGSearchResultType.RELATIONSHIP
                ):
                    context += f"[{it}]: Relationship - {search_result.content.subject} - {search_result.content.predicate} - {search_result.content.object}\n\n"
                else:
                    context += f"[{it}]: Community Name - {search_result.content.name}\n\nDescription - {search_result.content.summary}\n\n"

                it += 1
            total_results = (
                it - 1
            )  # Update total_results based on the last index used
        return context, total_results
