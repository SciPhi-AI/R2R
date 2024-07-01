import json
import logging
import uuid
from typing import Any, AsyncGenerator, Optional

from r2r.base import (
    AsyncPipe,
    AsyncState,
    EmbeddingProvider,
    PipeType,
    VectorDBProvider,
    VectorSearchResult,
    VectorSearchSettings,
)

from ..abstractions.search_pipe import SearchPipe

logger = logging.getLogger(__name__)


class VectorSearchPipe(SearchPipe):
    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
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
        self.vector_db_provider = vector_db_provider

    async def search(
        self,
        message: str,
        run_id: uuid.UUID,
        vector_search_settings: VectorSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        await self.enqueue_log(
            run_id=run_id, key="search_query", value=message
        )
        search_filters = (
            vector_search_settings.search_filters or self.config.search_filters
        )
        search_limit = (
            vector_search_settings.search_limit or self.config.search_limit
        )
        results = []
        query_vector = self.embedding_provider.get_embedding(
            message,
        )
        search_results = (
            self.vector_db_provider.hybrid_search(
                query_vector=query_vector,
                query_text=message,
                filters=search_filters,
                limit=search_limit,
            )
            if vector_search_settings.do_hybrid_search
            else self.vector_db_provider.search(
                query_vector=query_vector,
                filters=search_filters,
                limit=search_limit,
            )
        )
        reranked_results = self.embedding_provider.rerank(
            query=message, results=search_results, limit=search_limit
        )
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
        run_id: uuid.UUID,
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
