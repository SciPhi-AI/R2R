import asyncio
from abc import ABC, ABCMeta, abstractmethod, abstractproperty
from enum import Enum
from typing import Any, Optional, Type, AsyncGenerator

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

    def __init__(self, pipes: Optional[list[AsyncPipe]] = None, *args, **kwargs):
        self.pipes: list[AsyncPipe] = [] if pipes is None else pipes
        self.flow = PipeFlow.STANDARD

    def add_pipe(self, pipe: AsyncPipe):
        if self.pipes and self.pipes[-1].OUTPUT_TYPE != pipe.INPUT_TYPE:
            raise TypeError(
                "Output type of the last pipe does not match input type of the new pipe."
            )
        self.pipes.append(pipe)

    async def run(self, input):
        current_input = input
        for pipe in self.pipes:
            if pipe.flow == 'FAN_OUT':
                # Process each input independently and concurrently
                current_input = await asyncio.gather(*[pipe.run(item) for item in current_input])
            elif pipe.flow == 'FAN_IN':
                # Combine all inputs into a single list if necessary and process
                if isinstance(current_input[0], list):
                    current_input = [item for sublist in current_input for item in sublist]
                current_input = await pipe.run(current_input)
            else:
                # Process the input normally if STANDARD flow
                if isinstance(current_input, list):
                    current_input = await asyncio.gather(*[pipe.run(item) for item in current_input])
                else:
                    current_input = await pipe.run(current_input)
        return current_input

    # async def run(self, input: Any) -> Any:
    #     current_input = input
    #     for pipe in self.pipes:
    #         if self.flow == PipeFlow.STANDARD or self.flow == PipeFlow.FAN_IN:
    #             current_input = pipe.run(current_input)
    #         elif self.flow == PipeFlow.FAN_OUT:
    #             if not isinstance(current_input, list):
    #                 current_input = [current_input]  # Ensure it's a list even if single item
    #             # Launch all tasks concurrently for fan-out processing
    #             current_input = [pipe.run(item) for item in current_input]
    #             # current_input = await asyncio.gather(*tasks)
    #         # elif pipe.flow == PipeFlow.FAN_IN:
    #         #     # Gather all inputs into one list if not already a list
    #         #     test = await current_input
    #         #     print("test input = ", test)


    #         #     if not isinstance(current_input, list):
    #         #         current_input = [current_input]
    #         #     # Assuming we need to flatten and combine results, for example:
    #         #     combined_input = [item for sublist in test for item in sublist]
    #         #     print("combined_input = ", combined_input)
    #         #     current_input = await pipe.run(combined_input)
    #         if self.flow == PipeFlow.STANDARD:
    #             self.flow = pipe.flow
    #         elif self.flow == PipeFlow.FAN_OUT:
    #             if pipe.flow == PipeFlow.FAN_IN:
    #                 self.flow = PipeFlow.STANDARD
            
    #     print("current_input = ", current_input)
    #     # Process the final pipe's output
    #     if self.flow == PipeFlow.FAN_OUT:
    #         current_input = [await input for input in current_input]

    #     print("current_input post fan in = ", current_input)

    #     if not isinstance(current_input, AsyncGenerator):
    #         return await current_input
    #     else:
    #         # Handle async generator output differently
    #         # This could be an async for-loop or similar depending on caller's needs
    #         return current_input
