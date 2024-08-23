import json
import logging
from typing import Any, AsyncGenerator, Optional
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
        type: PipeType = PipeType.SEARCH,
        config: Optional[SearchPipe.SearchConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            type=type,
            config=config or SearchPipe.SearchConfig(),
            *args,
            **kwargs,
        )
        self.embedding_provider = embedding_provider
        self.database_provider = database_provider

    async def search(
        self,
        message: str,
        run_id: UUID,
        vector_search_settings: VectorSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        await self.enqueue_log(
            run_id=run_id, key="search_query", value=message
        )
        vector_search_settings.filters = (
            vector_search_settings.filters or self.config.filters
        )
        vector_search_settings.search_limit = (
            vector_search_settings.search_limit or self.config.search_limit
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
                search_settings=vector_search_settings,
            )
            if vector_search_settings.use_hybrid_search
            else self.database_provider.vector.semantic_search(
                query_vector=query_vector,
                search_settings=vector_search_settings,
            )
        )
        reranked_results = self.embedding_provider.rerank(
            query=message,
            results=search_results,
            limit=vector_search_settings.search_limit,
        )
        include_title_if_available = kwargs.get(
            "include_title_if_available", False
        )
        if include_title_if_available:
            for result in reranked_results:
                title = result.metadata.get("title", None)
                if title:
                    text = result.metadata.get("text", "")
                    result.text = f"Document Title:{title}\n\nText:{text}"

        for result in reranked_results:
            result.metadata["associatedQuery"] = message
            results.append(result)
            yield result

        await self.enqueue_log(
            run_id=run_id,
            key="search_results",
            value=json.dumps([ele.json() for ele in results]),
        )

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        search_queries = []
        search_results = []
        async for search_request in input.message:
            search_queries.append(search_request)
            async for result in self.search(
                message=search_request,
                run_id=run_id,
                vector_search_settings=vector_search_settings,
                *args,
                **kwargs,
            ):
                search_results.append(result)
                yield result

        await state.update(
            self.config.name, {"output": {"search_results": search_results}}
        )

        await state.update(
            self.config.name,
            {
                "output": {
                    "search_queries": search_queries,
                    "search_results": search_results,
                }
            },
        )
