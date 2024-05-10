import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import (
    AsyncContext,
    AsyncPipe,
    EmbeddingProvider,
    PipeFlow,
    PipeType,
    SearchResult,
    VectorDBProvider,
)

from ..abstractions.search import SearchPipe

logger = logging.getLogger(__name__)


class DefaultVectorSearchPipe(SearchPipe):
    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        embedding_provider: EmbeddingProvider,
        flow: PipeFlow = PipeFlow.STANDARD,
        type: PipeType = PipeType.SEARCH,
        config: Optional[SearchPipe.SearchConfig] = None,
        *args,
        **kwargs,
    ):
        logger.info(f"Initalizing an `DefaultVectorSearchPipe` pipe.")
        super().__init__(
            vector_db_provider=vector_db_provider,
            flow=flow,
            type=type,
            config=config or SearchPipe.SearchConfig(),
            *args,
            **kwargs,
        )
        self.embedding_provider = embedding_provider

    async def search(
        self,
        message: str,
    ) -> AsyncGenerator[SearchResult, None]:
        """
        Stores a batch of vector entries in the database.
        """
        for result in self.vector_db_provider.search(
            query_vector=self.embedding_provider.get_embedding(
                message,
            ),
            filters=self.config.filters,
            limit=self.config.limit,
        ):
            result.metadata["query"] = message
            yield result

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        context: AsyncContext,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[SearchResult, None]:
        for query in ["qq", "rr", "ss"]:
            yield query

        # search_results = []
        # if isinstance(input.message, AsyncGenerator):
        #     async for search_request in input.message:
        #         if isinstance(search_request, str):
        #             async for result in self.search(message=search_request):
        #                 search_results.append(result)
        #                 yield result
        # elif isinstance(input.message, str):
        #     async for result in self.search(message=input.message):
        #         search_results.append(result)
        #         yield result
        # else:
        #     raise TypeError("Input must be an AsyncGenerator or a string.")

        # await context.update(
        #     self.config.name, {"output": {"search_results": search_results}}
        # )
