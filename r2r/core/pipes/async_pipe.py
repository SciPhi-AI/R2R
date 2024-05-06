from abc import ABC, abstractmethod
from typing import Optional

from ..utils.logging import LoggingDatabaseConnection, log_output_to_db


class AsyncPipe(ABC):
    def __init__(
        self,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs
    ):
        self.logging_connection = logging_connection
        self.pipe_run_info: Optional[dict] = None
        self.is_async = True

    def _check_pipe_initialized(self) -> None:
        if self.pipe_run_info is None:
            raise ValueError(
                "The pipe has not been initialized. Please call `initialize_pipe` before running the pipe."
            )

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if isinstance(attr, property):
            return attr

        if callable(attr) and name not in [
            "__init__",
            "close",
            "_check_pipe_initialized",
            "__getattribute__",
            "initialize_pipe",
            "run",
        ]:

            def newfunc(*args, **kwargs):
                self._check_pipe_initialized()
                return attr(*args, **kwargs)

            return newfunc
        else:
            return attr

    def close(self):
        if self.logging_connection:
            self.logging_connection.__exit__(None, None, None)

    @abstractmethod
    def initialize_pipe(self, *args, **kwargs):
        pass

    @abstractmethod
    async def run(self, *args, **kwargs):
        pass

    @log_output_to_db
    def log(self, data: any) -> dict:
        """
        Extracts text from a document.
        """
        try:
            if not isinstance(data, dict):
                data = data.dict()
        except AttributeError:
            raise ValueError("Data must be convertable to a dictionary.")

        return data
