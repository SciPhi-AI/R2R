import logging
from typing import Any, Optional

from r2r.core import (
    AsyncState,
    PipeFlow,
    PipeLoggingConnectionSingleton,
    PipeType,
)

from ...core.pipes.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class CollectorPipe(LoggableAsyncPipe):
    def __init__(
        self,
        pipe_logger: Optional[PipeLoggingConnectionSingleton] = None,
        flow: PipeFlow = PipeFlow.FAN_IN,
        type: PipeType = PipeType.OTHER,
        config: Optional[LoggableAsyncPipe.PipeConfig] = None,
        *args,
        **kwargs
    ):
        super().__init__(
            flow=flow,
            type=type,
            config=config,
            pipe_logger=pipe_logger,
            *args,
            **kwargs
        )
        self.results: list[Any] = []

    async def collect(self, input: Any, state: AsyncState):
        for iterator in input.message:
            async for item in iterator:
                self.results.append(item)

    async def _run_logic(self, input: Any, state: AsyncState) -> Any:
        await self.collect(input, state)
        return self.results
