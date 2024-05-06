from typing import Any, Optional

from ..abstractions.pipes import AsyncPipe, PipeType
from ..utils.logging import LoggingDatabaseConnection, log_output_to_db


class LoggableAsyncPipe(AsyncPipe):
    def __init__(
        self,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs
    ):
        self.logging_connection = logging_connection
        super().__init__(*args, **kwargs)

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
