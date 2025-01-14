from typing import Any, AsyncGenerator
from uuid import UUID

from core.base import AsyncPipe, AsyncState, ChunkSearchResult, SearchSettings


class RoutingSearchPipe(AsyncPipe):
    def __init__(
        self,
        search_pipes: dict[str, AsyncPipe],
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
        search_settings: SearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[ChunkSearchResult, None]:
        search_pipe = self.search_pipes.get(search_settings.search_strategy)
        if not search_pipe:
            raise ValueError(
                f"Search strategy {search_settings.search_strategy} not found"
            )

        async for result in search_pipe._run_logic(  # type: ignore
            input,
            state,
            run_id,
            search_settings=search_settings,
            *args,
            **kwargs,
        ):
            yield result
