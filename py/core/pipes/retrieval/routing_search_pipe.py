from typing import Any, AsyncGenerator, Dict
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    VectorSearchResult,
    VectorSearchSettings,
)


class RoutingSearchPipe(AsyncPipe):
    def __init__(
        self,
        search_pipes: Dict[str, AsyncPipe],
        default_strategy: str,
        config: AsyncPipe.PipeConfig,
        *args,
        **kwargs,
    ):
        super().__init__(config, *args, **kwargs)
        self.search_pipes = search_pipes
        self.default_strategy = default_strategy

    async def _run_logic(  # type: ignore
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
        if not search_pipe:
            raise ValueError(
                f"Search strategy {vector_search_settings.search_strategy} not found"
            )

        async for result in search_pipe._run_logic(  # type: ignore
            input,
            state,
            run_id,
            vector_search_settings=vector_search_settings,
            *args,
            **kwargs,
        ):
            yield result
