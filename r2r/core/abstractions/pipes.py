from abc import ABC, ABCMeta, abstractmethod, abstractproperty
from enum import Enum
from typing import Any, Optional, Type

from ..utils import generate_run_id


class RunTypeChecker(ABCMeta):
    def __new__(cls, name, bases, namespace, **kwargs):
        if (
            "run" in namespace
            and "INPUT_TYPE" in namespace
            and "OUTPUT_TYPE" in namespace
        ):
            original_run = namespace["run"]

            def wrapped_run(
                self, input: namespace["INPUT_TYPE"], *args, **kwargs
            ) -> namespace["OUTPUT_TYPE"]:
                if not isinstance(input, namespace["INPUT_TYPE"]):
                    raise TypeError(
                        f"{self.__class__.__name__}: Expected input of type {namespace['INPUT_TYPE'].__name__}, got {type(input).__name__}"
                    )
                result = original_run(self, input, *args, **kwargs)
                if not isinstance(result, namespace["OUTPUT_TYPE"]):
                    raise TypeError(
                        f"{self.__class__.__name__}: Expected output of type {namespace['OUTPUT_TYPE'].__name__}, got {type(result).__name__}"
                    )
                return result

            namespace["run"] = wrapped_run
        return super().__new__(cls, name, bases, namespace)


class PipeType(Enum):
    PARSING = "parsing"
    EMBEDDING = "embedding"
    STORAGE = "storage"
    SEARCH = "search"
    OTHER = "other"


class PipeRunInfo:
    def __init__(self, run_id: str, type: PipeType) -> None:
        self.run_id = run_id
        self.type = type


class AsyncPipe(ABC, metaclass=RunTypeChecker):
    INPUT_TYPE = Type[Any]
    OUTPUT_TYPE = Type[Any]

    def __init__(self, *args, **kwargs):
        self.pipe_run_info: Optional[PipeRunInfo] = None
        self.is_async = True

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if isinstance(attr, property):
            return attr

        # Skip wrapping for these specific attributes or any non-callable attributes
        if name in [
            "INPUT_TYPE",
            "OUTPUT_TYPE",
            "__dict__",
            "__class__",
        ] or not callable(attr):
            return attr

        if callable(attr) and name not in [
            "__init__",
            "__getattribute__",
            "_check_pipe_initialized",
            "_initialize_pipe",
            "close",
            "run",
        ]:

            def newfunc(*args, **kwargs):
                self._check_pipe_initialized()
                return attr(*args, **kwargs)

            return newfunc
        else:
            return attr

    def _check_pipe_initialized(self) -> None:
        if self.pipe_run_info is None:
            raise ValueError(
                "The pipe has not been initialized. Please call `_initialize_pipe` before running the pipe."
            )

    def _initialize_pipe(self, *args, **kwargs) -> None:
        self.pipe_run_info = PipeRunInfo(
            generate_run_id(),
            self.pipe_type,
        )

    def close(self):
        pass

    @abstractproperty
    def pipe_type(self) -> PipeType:
        pass

    @abstractmethod
    async def run(self, input: INPUT_TYPE) -> OUTPUT_TYPE:
        pass


class Pipeline:
    def __init__(self):
        self.pipes: list[AsyncPipe] = []

    def add_pipe(self, pipe: AsyncPipe):
        if self.pipes and self.pipes[-1].OUTPUT_TYPE != pipe.INPUT_TYPE:
            raise TypeError(
                "Output type of the last pipe does not match input type of the new pipe."
            )
        self.pipes.append(pipe)

    async def run(self, input: Any) -> Any:
        for pipe in self.pipes:
            input = pipe.run(input)
        result = await input
        return result
