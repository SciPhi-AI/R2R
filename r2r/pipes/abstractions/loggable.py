from typing import Any, Optional

from ...core.abstractions.pipes import AsyncPipe, PipeConfig, PipeType
from ...core.utils.logging import (
    LoggingDatabaseConnectionSingleton,
    log_output_to_db,
)


class LoggableAsyncPipe(AsyncPipe):
    def __init__(
        self,
        config: PipeConfig,
        logging_connection: Optional[
            LoggingDatabaseConnectionSingleton
        ] = None,
        *args,
        **kwargs
    ):
        if not logging_connection:
            logging_connection = LoggingDatabaseConnectionSingleton()
        self.logging_connection = logging_connection
        super().__init__(config, *args, **kwargs)

    def close(self):
        if self.logging_connection:
            self.logging_connection.__exit__(None, None, None)

    @log_output_to_db
    def log(self, data: Any) -> dict:
        """
        Extracts text from a document.
        """
        try:
            if not isinstance(data, dict):
                data = data.dict()
        except AttributeError:
            raise ValueError("Data must be convertable to a dictionary.")

        return data
