import logging
from typing import Any, Optional

from r2r.core import (
    AsyncContext,
    LoggingDatabaseConnectionSingleton,
    PipeConfig,
    PipeFlow,
    PipeType,
)

from .loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class AggregatorPipe(LoggableAsyncPipe):
    def __init__(
        self,
        logging_connection: Optional[
            LoggingDatabaseConnectionSingleton
        ] = None,
        flow: PipeFlow = PipeFlow.FAN_IN,
        type: PipeType = PipeType.OTHER,
        config: Optional[PipeConfig] = None,
        *args,
        **kwargs
    ):
        super().__init__(
            flow=flow,
            type=type,
            config=config,
            logging_connection=logging_connection,
            *args,
            **kwargs
        )
        self.results: list[Any] = []

    async def aggregate(self, input: Any, context: AsyncContext):
        for iterator in input.message:
            async for item in iterator:
                self.results.append(item)
            # Optionally, process or transform the item here

    async def _run_logic(self, input: Any, context: AsyncContext) -> Any:
        await self.aggregate(input, context)
        return self.results
