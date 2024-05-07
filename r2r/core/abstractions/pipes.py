import asyncio
from abc import ABC, ABCMeta, abstractmethod, abstractproperty
from enum import Enum
from typing import Any, AsyncGenerator, Optional, Type

from ..utils import generate_run_id


class RunTypeChecker(ABCMeta):
    def __new__(cls, name, bases, namespace, *args, **kwargs):
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
    RAG = "rag"
    OTHER = "other"


class PipeFlow(Enum):
    STANDARD = "standard"
    FAN_OUT = "fan_out"
    FAN_IN = "fan_in"


class PipeRunInfo:
    def __init__(self, run_id: str, type: PipeType) -> None:
        self.run_id = run_id
        self.type = type


class AsyncPipe(ABC, metaclass=RunTypeChecker):
    INPUT_TYPE = Type[Any]
    OUTPUT_TYPE = Type[Any]
    FLOW = PipeFlow.STANDARD

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
            self.type,
        )

    @property
    def flow(self) -> PipeFlow:
        return self.FLOW

    def close(self):
        pass

    @abstractproperty
    def type(self) -> PipeType:
        pass

    @abstractmethod
    async def run(self, input: INPUT_TYPE) -> OUTPUT_TYPE:
        pass


class Pipeline:
    INPUT_TYPE = Type[Any]
    OUTPUT_TYPE = Type[Any]

    def __init__(
        self, pipes: Optional[list[AsyncPipe]] = None, *args, **kwargs
    ):
        self.pipes: list[AsyncPipe] = [] if pipes is None else pipes
        self.flow = PipeFlow.STANDARD

    def add_pipe(self, pipe: AsyncPipe):
        if self.pipes and self.pipes[-1].OUTPUT_TYPE != pipe.INPUT_TYPE:
            raise TypeError(
                "Output type of the last pipe does not match input type of the new pipe."
            )
        self.pipes.append(pipe)

    async def run(self, input: Any) -> Any:
        current_input = input
        for pipe in self.pipes:
            if self.flow == PipeFlow.STANDARD:
                if pipe.flow == PipeFlow.FAN_OUT:
                    self.flow = PipeFlow.FAN_OUT
                elif pipe.flow == PipeFlow.FAN_IN:
                    raise ValueError(
                        "A FAN_IN pipe cannot be processed while in STANDARD flow."
                    )

            elif self.flow == PipeFlow.FAN_OUT:
                if pipe.flow == PipeFlow.STANDARD:
                    current_input = await self.handle_standard_flow(
                        current_input
                    )
                elif pipe.flow == PipeFlow.FAN_OUT:
                    raise ValueError(
                        "A FAN_OUT pipe cannot be processed while in FAN_OUT flow."
                    )
                elif pipe.flow == PipeFlow.FAN_IN:
                    # Presumably, handling for transitioning to FAN_IN flow
                    self.flow = PipeFlow.FAN_IN
            current_input = await self.execute_pipe(pipe, current_input)

        return current_input

    async def handle_standard_flow(self, current_input):
        if asyncio.iscoroutine(current_input):
            current_input = await current_input
        if not hasattr(current_input, "__aiter__"):
            raise TypeError("Expected an async generator, got something else")
        return current_input

    async def execute_pipe(self, pipe, current_input):
        if self.flow == PipeFlow.FAN_OUT and hasattr(
            current_input, "__aiter__"
        ):
            # Process each item concurrently if the current flow is FAN_OUT
            return [await pipe.run(item) async for item in current_input]
        else:
            # Check if the pipe function is a coroutine function and execute accordingly
            return (
                await pipe.run(current_input)
                if asyncio.iscoroutinefunction(pipe.run)
                else pipe.run(current_input)
            )

    # async def run(self, input: Any) -> Any:
    #     current_input = input

    #     for pipe in self.pipes:
    #         if self.flow == PipeFlow.STANDARD:
    #             if pipe.flow == PipeFlow.STANDARD:
    #                 pass
    #             elif pipe.flow == PipeFlow.FAN_OUT:
    #                 self.flow = PipeFlow.FAN_OUT
    #             elif pipe.flow == PipeFlow.FAN_IN:
    #                 raise ValueError("A FAN_IN pipe cannot be processed while in STANDARD flow.")
    #             current_input = pipe.run(current_input)

    #         elif self.flow == PipeFlow.FAN_OUT:
    #             if pipe.flow == PipeFlow.STANDARD:
    #                 if asyncio.iscoroutine(current_input):
    #                     current_input = await current_input
    #                 if not hasattr(current_input, '__aiter__'):
    #                     raise TypeError("Expected an async generator, got something else")
    #                 current_input = [await pipe.run(item) async for item in current_input]
    #             elif pipe.flow == PipeFlow.FAN_OUT:
    #                 raise ValueError("A FAN_OUT pipe cannot be processed while in FAN_OUT flow.")
    #             elif pipe.flow == PipeFlow.FAN_IN:
    #                 current_input = pipe.run(current_input)

    #     if asyncio.iscoroutine(current_input):
    #         return await current_input
    #     else:
    #         return current_input
