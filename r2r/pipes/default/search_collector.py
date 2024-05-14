import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import AsyncPipe, AsyncState, PipeType, SearchResult

from ..abstractions.collector import CollectorPipe

logger = logging.getLogger(__name__)


class DefaultSearchCollectorPipe(CollectorPipe):
    class Input(CollectorPipe.Input):
        message: AsyncGenerator[SearchResult, None]

    def __init__(
        self,
        type: PipeType = PipeType.COLLECTOR,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        logger.info(f"Initalizing an `DefaultSearchCollectorPipe` pipe.")
        super().__init__(
            type=type,
            config=config
            or AsyncPipe.PipeConfig(name="default_search_collector"),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        await self.collect(input, state)
        if len(self.results) > 0:
            search_context = ""
            for iteration, result in enumerate(self.results):
                search_context += (
                    f"Result {iteration+1}:\n{result.metadata['text']}\n\n"
                )
        else:
            search_context = "No results found."

        await state.update(
            self.config.name, {"output": {"search_context": search_context}}
        )
        yield search_context
