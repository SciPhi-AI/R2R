from abc import ABC, abstractmethod
from typing import Optional

from ..providers.logging import LoggingDatabaseConnection


class Pipeline(ABC):
    def __init__(
        self,
        logging_provider: Optional[LoggingDatabaseConnection] = None,
        **kwargs
    ):
        self.logging_provider = logging_provider

        self.pipeline_run_info = None

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
            "close",
            "_check_pipeline_initialized",
            "__getattribute__",
            "initialize_pipeline",
            "run",
        ]:

            def newfunc(*args, **kwargs):
                self._check_pipeline_initialized()
                return attr(*args, **kwargs)

            return newfunc
        else:
            return attr

    def close(self):
        if self.logging_provider:
            self.logging_provider.__exit__(None, None, None)

    @abstractmethod
    def initialize_pipeline(self, **kwargs):
        pass

    @abstractmethod
    def run(self, **kwargs):
        pass
