from typing import Any, Optional

from .base import AsyncPipe, PipeFlow, PipeType
from .logging import (
    LoggingDatabaseConnectionSingleton,
)


class LoggableAsyncPipe(AsyncPipe):
    def __init__(
        self,
        logging_connection: Optional[
            LoggingDatabaseConnectionSingleton
        ] = None,
        flow: PipeFlow = PipeFlow.STANDARD,
        type: PipeType = PipeType.OTHER,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs
    ):
        if not logging_connection:
            logging_connection = LoggingDatabaseConnectionSingleton()
        self.logging_connection = logging_connection
        super().__init__(flow=flow, type=type, config=config, *args, **kwargs)

    def close(self):
        if self.logging_connection:
            self.logging_connection.__exit__(None, None, None)