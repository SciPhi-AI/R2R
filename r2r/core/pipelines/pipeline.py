from abc import ABC, abstractmethod
from typing import Optional

from ..utils.logging import LoggingDatabaseConnection, log_output_to_db


class Pipeline(ABC):
    def __init__(
        self,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs
    ):
        self.logging_connection = logging_connection
        self.pipeline_run_info: Optional[dict] = None
        self.is_async = False

    def _check_pipeline_initialized(self) -> None:
        if self.pipeline_run_info is None:
            raise ValueError(
                "The pipeline has not been initialized. Please call `initialize_pipeline` before running the pipeline."
            )

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if isinstance(attr, property):
            return attr

        if callable(attr) and name not in [
            "__init__",
            "__getattribute__",
            "_check_pipeline_initialized",
            "close",
            "initialize_pipeline",
            "run",
            "run_stream",
        ]:

            def newfunc(*args, **kwargs):
                self._check_pipeline_initialized()
                return attr(*args, **kwargs)

            return newfunc
        else:
            return attr

    def close(self):
        if self.logging_connection:
            self.logging_connection.__exit__(None, None, None)

    @abstractmethod
    def initialize_pipeline(self, *args, **kwargs):
        pass

    @abstractmethod
    def run(self, *args, **kwargs):
        pass

    @abstractmethod
    def run_stream(self, *args, **kwargs):
        """
        Runs the pipeline in streaming mode.
        """
        raise NotImplementedError(
            "Streaming mode is not supported default for `Pipeline`."
        )

    @log_output_to_db
    def log(self, data: any) -> dict:
        """
        Extracts text from a document.
        """
        try:
            data = data.dict()
        except AttributeError:
            raise ValueError("Data must be convertable to a dictionary.")

        return data.dict()
