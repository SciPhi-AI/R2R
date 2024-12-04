import json
import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    ChunkSearchResult,
    DatabaseProvider,
    EmbeddingProvider,
    EmbeddingPurpose,
    SearchSettings,
)

from ..abstractions.search_pipe import SearchPipe

logger = logging.getLogger()


class VectorSearchPipe(SearchPipe):
    def __init__(
        self,
        database_provider: DatabaseProvider,
        embedding_provider: EmbeddingProvider,
        config: SearchPipe.SearchConfig,
        *args,
        **kwargs,
    ):
        super().__init__(
            config,
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
        search_settings: SearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[ChunkSearchResult, None]:
        if search_settings.chunk_settings.enabled == False:
            return

        search_settings.filters = (
            search_settings.filters or self.config.filters
        )
        search_settings.limit = search_settings.limit or self.config.limit
        results = []
        query_vector = await self.embedding_provider.async_get_embedding(
            message,
            purpose=EmbeddingPurpose.QUERY,
        )

        if (
            search_settings.use_fulltext_search
            and search_settings.use_semantic_search
        ) or search_settings.use_hybrid_search:

            search_results = await self.database_provider.hybrid_search(
                query_vector=query_vector,
                query_text=message,
                search_settings=search_settings,
            )
        elif search_settings.use_fulltext_search:
            search_results = await self.database_provider.full_text_search(
                query_text=message,
                search_settings=search_settings,
            )
        elif search_settings.use_semantic_search:
            search_results = await self.database_provider.semantic_search(
                query_vector=query_vector,
                search_settings=search_settings,
            )
        else:
            raise ValueError(
                "At least one of use_fulltext_search or use_semantic_search must be True"
            )

        reranked_results = await self.embedding_provider.arerank(
            query=message,
            results=search_results,
            limit=search_settings.limit,
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
        search_settings: SearchSettings = SearchSettings(),
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[ChunkSearchResult, None]:
        async for search_request in input.message:
            await self.enqueue_log(
                run_id=run_id, key="search_query", value=search_request
            )

            search_results = []
            async for result in self.search(
                search_request,
                search_settings,
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
