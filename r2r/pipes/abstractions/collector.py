import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import (
    AsyncState,
    PipeFlow,
    PipeLoggingConnectionSingleton,
    PipeType,
)

from ...core.pipes.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class CollectorPipe(LoggableAsyncPipe):
    class Input(LoggableAsyncPipe.Input):
        message: AsyncGenerator[AsyncGenerator[Any, None], None]

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
        async for item in input.message:
            self.results.append(item)
