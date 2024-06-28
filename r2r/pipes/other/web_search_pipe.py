import json
import logging
import uuid
from typing import Any, AsyncGenerator, Optional

from r2r.base import (
    AsyncPipe,
    AsyncState,
    PipeType,
    VectorSearchResult,
    generate_id_from_label,
)
from r2r.integrations import SerperClient

from ..abstractions.search_pipe import SearchPipe

logger = logging.getLogger(__name__)


class WebSearchPipe(SearchPipe):
    def __init__(
        self,
        serper_client: SerperClient,
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
        self.serper_client = serper_client

    async def search(
        self,
        message: str,
        run_id: uuid.UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        search_limit_override = kwargs.get("search_limit", None)
        await self.enqueue_log(
            run_id=run_id, key="search_query", value=message
        )
        # TODO - Make more general in the future by creating a SearchProvider interface
        results = self.serper_client.get_raw(
            query=message,
            limit=search_limit_override or self.config.search_limit,
        )

        search_results = []
        for result in results:
            if result.get("snippet") is None:
                continue
            result["text"] = result.pop("snippet")
            search_result = VectorSearchResult(
                id=generate_id_from_label(str(result)),
                score=result.get(
                    "score", 0
                ),  # TODO - Consider dynamically generating scores based on similarity
                metadata=result,
            )
            search_results.append(search_result)
            yield search_result

        await self.enqueue_log(
            run_id=run_id,
            key="search_results",
            value=json.dumps([ele.json() for ele in search_results]),
        )

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        *args: Any,
        **kwargs,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        search_queries = []
        search_results = []
        async for search_request in input.message:
            search_queries.append(search_request)
            async for result in self.search(
                message=search_request, run_id=run_id, *args, **kwargs
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
