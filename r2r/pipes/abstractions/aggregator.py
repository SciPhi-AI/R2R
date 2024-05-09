import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, List, Optional

from r2r.core import (
    AsyncContext,
    LoggingDatabaseConnectionSingleton,
    PipeConfig,
    PipeFlow,
    PipeType,
)

from ..abstractions.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class AggregatorPipe(LoggableAsyncPipe):
    def __init__(
        self,
        config: PipeConfig,
        logging_connection: Optional[
            LoggingDatabaseConnectionSingleton
        ] = None,
        *args,
        **kwargs
    ):
        super().__init__(
            config=config,
            logging_connection=logging_connection,
            *args,
            **kwargs
        )
        self.config = config
        self.results: list[Any] = []

    @property
    def type(self) -> PipeType:
        return PipeType.AGGREGATOR

    @property
    def flow(self) -> PipeFlow:
        return PipeFlow.FAN_IN

    async def aggregate(self, input: Any, context: AsyncContext):
        async for item in input.message:
            self.results.append(item)
            # Optionally, process or transform the item here

    async def _run_logic(self, input: Any, context: AsyncContext) -> Any:
        await self.aggregate(input, context)
        print("returning self.results = ", self.results)
        return self.results
