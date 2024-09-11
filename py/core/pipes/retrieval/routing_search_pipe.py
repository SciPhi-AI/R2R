from typing import Any, AsyncGenerator, Dict, Optional, Type
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    VectorSearchResult,
    VectorSearchSettings,
)

from ..abstractions.search_pipe import SearchPipe


class RoutingSearchPipe(SearchPipe):
    def __init__(
        self,
        search_pipes: Dict[str, SearchPipe],
        default_strategy: str,
        config: Optional[SearchPipe.SearchConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            config=config or SearchPipe.SearchConfig(), *args, **kwargs
        )
        self.search_pipes = search_pipes
        self.default_strategy = default_strategy

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        vector_search_settings: VectorSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[VectorSearchResult, None]:
        search_pipe = self.search_pipes.get(
            vector_search_settings.search_strategy
        )

        async for result in search_pipe._run_logic(
            input,
            state,
            run_id,
            vector_search_settings=vector_search_settings,
            *args,
            **kwargs,
        ):
            yield result
