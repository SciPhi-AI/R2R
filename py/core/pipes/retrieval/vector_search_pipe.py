import json
import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    DatabaseProvider,
    EmbeddingProvider,
    EmbeddingPurpose,
    PipeType,
    VectorSearchResult,
    VectorSearchSettings,
)

from ..abstractions.search_pipe import SearchPipe

logger = logging.getLogger(__name__)


class VectorSearchPipe(SearchPipe):
    def __init__(
        self,
        database_provider: DatabaseProvider,
        embedding_provider: EmbeddingProvider,
        config: SearchPipe.SearchConfig,
        type: PipeType = PipeType.SEARCH,
        *args,
        **kwargs,
    ):
        super().__init__(
            config,
            type,
            *args,
            **kwargs,
        )
        self.embedding_provider = embedding_provider
        self.database_provider = database_provider

        self._config: SearchPipe.SearchConfig = config

    @property
    def config(self) -> SearchPipe.SearchConfig:
        return self._config

    async def search(  # type: ignore
        self,
        message: str,
        search_settings: VectorSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        search_settings.filters = (
            search_settings.filters or self.config.filters
        )
        search_settings.search_limit = (
            search_settings.search_limit or self.config.search_limit
        )
        results = []
        query_vector = self.embedding_provider.get_embedding(
            message,
            purpose=EmbeddingPurpose.QUERY,
        )

        search_results = (
            self.database_provider.vector.hybrid_search(
                query_vector=query_vector,
                query_text=message,
                search_settings=search_settings,
            )
            if search_settings.use_hybrid_search
            else self.database_provider.vector.semantic_search(
                query_vector=query_vector,
                search_settings=search_settings,
            )
        )
        reranked_results = self.embedding_provider.rerank(
            query=message,
            results=search_results,
            limit=search_settings.search_limit,
        )
        if kwargs.get("include_title_if_available", False):
            for result in reranked_results:
                if title := result.metadata.get("title", None):
                    text = result.text
                    result.text = f"Document Title:{title}\n\nText:{text}"

        for result in reranked_results:
            result.metadata["associated_query"] = message
            results.append(result)
            yield result

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        async for search_request in input.message:
            await self.enqueue_log(
                run_id=run_id, key="search_query", value=search_request
            )

            search_results = []
            async for result in self.search(
                search_request,
                vector_search_settings,
                *args,
                **kwargs,
            ):
                search_results.append(result)
                yield result

            await self.enqueue_log(
                run_id=run_id,
                key="search_results",
                value=json.dumps([ele.json() for ele in search_results]),
            )

            await state.update(
                self.config.name,
                {"output": {"search_results": search_results}},
            )

            await state.update(
                self.config.name,
                {
                    "output": {
                        "search_query": search_request,
                        "search_results": search_results,
                    }
                },
            )
