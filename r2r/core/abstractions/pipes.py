import asyncio
import inspect
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel


class PipeFlow(Enum):
    STANDARD = "standard"
    FAN_OUT = "fan_out"
    FAN_IN = "fan_in"


class PipeType(Enum):
    QUERY_TRANSFORM = "query_transform"
    SEARCH = "search"


class PipeRunInfo(BaseModel):
    run_id: uuid.UUID
    type: PipeType


class AsyncPipe(ABC):
    class PipeConfig(BaseModel):
        name: str

        class Config:
            extra = "forbid"
            arbitrary_types_allowed = True

    class Input(BaseModel):
        message: Any

        class Config:
            extra = "forbid"
            arbitrary_types_allowed = True

    def __init__(
        self,
        config: Optional[PipeConfig] = None,
        flow: PipeFlow = PipeFlow.STANDARD,
    ):
        self.config = config or self.Config()
        self._flow = flow

    @property
    def flow(self) -> PipeFlow:
        return self._flow

    async def run(
        self, input: Input, context: Any
    ) -> AsyncGenerator[Any, None]:
        return self._run_logic(input, context)

    @abstractmethod
    async def _run_logic(
        self, input: Input, context: Any
    ) -> AsyncGenerator[Any, None]:
        pass


class AsyncContext:
    def __init__(self):
        self.data = {}
        self.lock = asyncio.Lock()

    async def update(self, outer_key: str, values: dict):
        async with self.lock:
            if not isinstance(values, dict):
                raise ValueError("Values must be contained in a dictionary.")
            if outer_key not in self.data:
                self.data[outer_key] = {}
            for inner_key, inner_value in values.items():
                self.data[outer_key][inner_key] = inner_value

    async def get(self, outer_key: str, inner_key: str, default=None):
        async with self.lock:
            if outer_key not in self.data:
                raise ValueError(
                    f"Key {outer_key} does not exist in the context."
                )
            if inner_key not in self.data[outer_key]:
                return default or {}
            return self.data[outer_key][inner_key]

    async def delete(self, outer_key: str, inner_key: Optional[str] = None):
        async with self.lock:
            if outer_key in self.data and not inner_key:
                del self.data[outer_key]
            else:
                if inner_key not in self.data[outer_key]:
                    raise ValueError(
                        f"Key {inner_key} does not exist in the context."
                    )
                del self.data[outer_key][inner_key]


class Pipeline:
    def __init__(self, context: Optional[AsyncContext] = None):
        self.pipes: list[AsyncPipe] = []
        self.upstream_outputs: list[list[dict[str, str]]] = []
        self.context = context or AsyncContext()
        self.futures = {}  # Dictionary to store futures of each pipe's output
        self.level = 0

    async def add_pipe(
        self,
        pipe: AsyncPipe,
        add_upstream_outputs: Optional[list[dict[str, str]]] = None,
        *args,
        **kwargs,
    ) -> None:
        self.pipes.append(pipe)
        if not add_upstream_outputs:
            add_upstream_outputs = []
        self.upstream_outputs.append(add_upstream_outputs)
        self.futures[pipe.config.name] = asyncio.Future()
        await self.context.update(pipe.config.name, {"settings": {}})

    async def run(self, input):
        current_input = input
        for pipe, add_upstream_output in zip(self.pipes, self.upstream_outputs):
            if pipe.flow == PipeFlow.FAN_OUT:
                if self.level == 0:
                    current_input = await self._run_pipe(pipe, current_input, add_upstream_output)
                    self.level += 1
                elif self.level == 1:
                    raise ValueError("Fan out not supported at level 1")
            elif pipe.flow == PipeFlow.STANDARD:
                if self.level == 0:
                    current_input = await self._run_pipe(pipe, current_input, add_upstream_output)
                elif self.level == 1:
                    current_input = [
                        await self._run_pipe(pipe, item, add_upstream_output)
                        async for item in current_input
                    ]
            elif pipe.flow == PipeFlow.FAN_IN:
                if self.level == 0:
                    raise ValueError("Fan in not supported at level 0")
                if self.level == 1:
                    current_input = await self._run_pipe(pipe, current_input, add_upstream_output)
                    self.level -= 1
            self.futures[pipe.config.name].set_result(current_input)

        if inspect.isasyncgen(current_input):
            final_result = []
            async for item in current_input:
                final_result.append(item)
            return final_result
        else:
            return await current_input

    async def _run_pipe(self, pipe, input, add_upstream_outputs):
        # Collect inputs, waiting for the necessary futures
        input_dict = {"message": input}
        for upstream_input in add_upstream_outputs:
            upstream_pipe_name = upstream_input["prev_pipe_name"]
            async def resolve_future_output(future):
                result = future.result()
                if inspect.isasyncgen(result):
                    # consume the async generator
                    [item async for item in result]
                else:
                    await result
            await resolve_future_output(self.futures[upstream_pipe_name])
            outputs = await self.context.get(
                upstream_input["prev_pipe_name"], "output"
            )
            input_dict[upstream_input["input_field"]] = outputs[upstream_input["prev_output_field"]]
            print('input_dict = ', input_dict)
        # Execute the pipe with all inputs resolved
        return await pipe.run(pipe.Input(**input_dict), self.context)

# class Pipeline:
#     def __init__(self, context: Optional[AsyncContext] = None):
#         self.pipes: list[AsyncPipe] = []
#         self.upstream_outputs: list[list[dict[str, str]]] = []
#         self.context = context or AsyncContext()
#         self.level = 0

#     async def add_pipe(
#         self,
#         pipe: AsyncPipe,
#         add_upstream_outputs: Optional[list[dict[str, str]]] = None,
#         *args,
#         **kwargs,
#     ) -> None:
#         # if self.pipes and self.pipes[-1].OUTPUT_TYPE != pipe.INPUT_TYPE:
#         #     raise TypeError(
#         #         "Output type of the last pipe does not match input type of the new pipe."
#         #     )
#         self.pipes.append(pipe)
#         if not add_upstream_outputs:
#             add_upstream_outputs = []
#         self.upstream_outputs.append(add_upstream_outputs)
#         await self.context.update(pipe.config.name, {"settings": {}})

#     async def run(self, input):
#         current_input = input
#         for pipe, add_upstream_output in zip(
#             self.pipes, self.upstream_outputs
#         ):
#             if pipe.flow == PipeFlow.FAN_OUT:
#                 if self.level == 0:
#                     current_input = await self._run_pipe(
#                         pipe, current_input, add_upstream_output
#                     )
#                     self.level += 1
#                 elif self.level == 1:
#                     raise ValueError("Fan out not supported at level 1")
#             elif pipe.flow == PipeFlow.STANDARD:
#                 if self.level == 0:
#                     current_input = await self._run_pipe(
#                         pipe, current_input, add_upstream_output
#                     )
#                 if self.level == 1:
#                     current_input = [
#                         await self._run_pipe(pipe, item, add_upstream_output)
#                         async for item in current_input
#                     ]
#             elif pipe.flow == PipeFlow.FAN_IN:
#                 if self.level == 0:
#                     raise ValueError("Fan in not supported at level 0")
#                 if self.level == 1:
#                     current_input = await self._run_pipe(
#                         pipe, current_input, add_upstream_output
#                     )
#                     self.level -= 1

#         if inspect.isasyncgen(current_input):
#             final_result = []
#             async for item in current_input:
#                 final_result.append(item)
#             return final_result
#         else:
#             return current_input

#     async def _run_pipe(
#         self,
#         pipe,
#         input,
#         add_upstream_outputs: list,
#     ):
#         input_dict = {"message": input}
#         for upstream_input in add_upstream_outputs:
#             outputs = await self.context.get(
#                 upstream_input["prev_pipe_name"], "output"
#             )
#             input_dict[upstream_input["input_field"]] = outputs[
#                 upstream_input["prev_output_field"]
#             ]
#         return await pipe.run(
#             pipe.Input(**input_dict), self.context
#         )


class PipeConfig:
    pass


# import asyncio
# import logging
# import uuid
# from abc import ABC, abstractmethod
# from copy import copy
# from dataclasses import dataclass
# from enum import Enum
# from typing import (
#     Any,
#     AsyncGenerator,
#     Generic,
#     Optional,
#     Type,
#     TypeVar,
#     Union,
#     final,
#     get_type_hints,
# )

# from pydantic import BaseModel, ValidationError
# import inspect
# from ..utils import generate_run_id

# logger = logging.getLogger(__name__)


# class PipeType(Enum):
#     AGGREGATOR = "aggregator"
#     EMBEDDING = "embedding"
#     OTHER = "other"
#     PARSING = "parsing"
#     QUERY_TRANSFORM = "query_transform"
#     SEARCH = "search"
#     RAG = "rag"
#     STORAGE = "storage"


# class PipeFlow(Enum):
#     STANDARD = "standard"
#     FAN_OUT = "fan_out"
#     FAN_IN = "fan_in"


# class PipeRunInfo(BaseModel):
#     run_id: uuid.UUID
#     type: PipeType


# @dataclass
# class PipeConfig(ABC):
#     """A base pipe configuration class"""

#     name: str


# class AsyncContext:
#     def __init__(self):
#         self.data = {}
#         self.lock = asyncio.Lock()

#     async def update(self, outer_key: str, values: dict):
#         async with self.lock:
#             if not isinstance(values, dict):
#                 raise ValueError("Values must be contained in a dictionary.")
#             if outer_key not in self.data:
#                 self.data[outer_key] = {}
#             for inner_key, inner_value in values.items():
#                 self.data[outer_key][inner_key] = inner_value

#     async def get(self, outer_key: str, inner_key: str, default=None):
#         async with self.lock:
#             if outer_key not in self.data:
#                 raise ValueError(
#                     f"Key {outer_key} does not exist in the context."
#                 )
#             if inner_key not in self.data[outer_key]:
#                 return default or {}
#             return self.data[outer_key][inner_key]

#     async def delete(self, outer_key: str, inner_key: Optional[str] = None):
#         async with self.lock:
#             if outer_key in self.data and not inner_key:
#                 del self.data[outer_key]
#             else:
#                 if inner_key not in self.data[outer_key]:
#                     raise ValueError(
#                         f"Key {inner_key} does not exist in the context."
#                     )
#                 del self.data[outer_key][inner_key]


# TInput = TypeVar("TInput")
# TOutput = TypeVar("TOutput")


# class AsyncPipe(Generic[TInput, TOutput], ABC):
#     class Input(BaseModel):
#         message: TInput
#         config_overrides: Optional[dict] = None

#         class Config:
#             arbitrary_types_allowed = True
#             extra = "forbid"

#     def __init__(self, config: PipeConfig, *args, **kwargs):
#         self.__class__.CONFIG_TYPE = type(config)
#         self._config = config

#         self.pipe_run_info: Optional[PipeRunInfo] = None
#         self.is_async = True

#         type_hints = get_type_hints(self.run)
#         self.INPUT_TYPE = type_hints.get("input")
#         self.OUTPUT_TYPE = type_hints.get("return")

#         if type(self).run is not AsyncPipe.run:
#             raise TypeError("Subclasses may not override the run() method.")
#         super().__init__(*args, **kwargs)

#     def _check_pipe_initialized(self) -> None:
#         if self.pipe_run_info is None:
#             raise ValueError(
#                 "The pipe has not been initialized. Please call `_initialize_pipe` before running the pipe."
#             )

#     async def _initialize_pipe(
#         self,
#         input: TInput,
#         context: AsyncContext,
#         config_overrides: Optional[dict] = None,
#         *args,
#         **kwargs,
#     ) -> None:
#         self.pipe_run_info = PipeRunInfo(
#             run_id=generate_run_id(),
#             type=self.type,
#         )
#         if not config_overrides:
#             config_overrides = {}
#         self._update_config(**config_overrides)

#     def _update_config(self, config_overrides: Optional[dict] = None) -> None:
#         config_overrides = config_overrides or {}
#         try:
#             # Update the existing config dictionary with the new overrides
#             # Use the setter to apply the updated configuration
#             self.config = {**self.config.dict(), **config_overrides}
#         except ValidationError as e:
#             logger.error(f"Configuration validation error: {e}")
#             raise

#     @property
#     def config(self) -> PipeConfig:
#         return self._config

#     @property
#     def do_await(self) -> bool:
#         return False

#     @config.setter
#     def config(self, value: Union[dict, PipeConfig]):
#         if isinstance(value, dict):
#             # Dynamically create an instance of CONFIG_TYPE from a dictionary
#             if self.__class__.CONFIG_TYPE is not None:
#                 self._config = self.__class__.CONFIG_TYPE(**value)
#             else:
#                 raise ValueError("CONFIG_TYPE is not set for this class.")
#         elif isinstance(value, PipeConfig):
#             # Check if the instance type is compatible
#             if isinstance(value, self.__class__.CONFIG_TYPE):
#                 self._config = value
#             else:
#                 raise TypeError(
#                     f"Config must be an instance of {self.__class__.CONFIG_TYPE.__name__}"
#                 )
#         else:
#             raise TypeError(
#                 "Config must be a dictionary or an instance of the defined CONFIG_TYPE"
#             )

#     @final
#     async def run(self, input: TInput, context: AsyncContext) -> TOutput:
#         await self._initialize_pipe(input, context)
#         return self._run_logic(input, context)

#     @property
#     @abstractmethod
#     def flow(self) -> PipeFlow:
#         pass

#     @property
#     @abstractmethod
#     def type(self) -> PipeType:
#         pass

#     @abstractmethod
#     def input_from_dict(self, input_dict: dict) -> TInput:
#         pass

#     @abstractmethod
#     async def _run_logic(
#         self, input: TInput, context: AsyncContext
#     ) -> TOutput:
#         pass


# class Pipeline:
#     def __init__(self):
#         self.pipes = []
#         self.level = 0

#     async def add_pipe(
#         self,
#         pipe: AsyncPipe,
#         add_upstream_outputs: Optional[dict] = None,
#         *args,
#         **kwargs,
#     ) -> None:
#         # if self.pipes and self.pipes[-1].OUTPUT_TYPE != pipe.INPUT_TYPE:
#         #     raise TypeError(
#         #         "Output type of the last pipe does not match input type of the new pipe."
#         #     )
#         self.pipes.append(pipe)
#         # if not add_upstream_outputs:
#         #     add_upstream_outputs = {}
#         # self.upstream_inputs_mapping.append(add_upstream_outputs)
#         # self.config_aggregator.register_pipe(pipe)
#         # await self.context.update(pipe.config.name, {"settings": {}})

#     async def run(self, input, context = None):
#         current_input = input
#         for pipe in self.pipes:
#             print("pipe = ", pipe)
#             print("current_input = ", current_input)
#             if pipe.flow == PipeFlow.FAN_OUT:
#                 if self.level == 0:
#                     current_input = await self._run_pipe(pipe, current_input, context)
#                     self.level += 1
#                 elif self.level == 1:
#                     raise ValueError("Fan out not supported at level 1")
#             elif pipe.flow == PipeFlow.STANDARD:
#                 if self.level == 0:
#                     current_input = await self._run_pipe(pipe, current_input, context)
#                 if self.level == 1:
#                     current_input = [
#                         await self._run_pipe(pipe, item, context) async for item in current_input
#                     ]
#             elif pipe.flow == PipeFlow.FAN_IN:
#                 if self.level == 0:
#                     raise ValueError("Fan in not supported at level 0")
#                 if self.level == 1:
#                     current_input = await self._run_pipe(pipe, current_input, context)
#                     self.level -= 1
#         print("current_input = ", current_input)
#         if inspect.isasyncgen(current_input):
#             final_result = []
#             async for item in current_input:
#                 final_result.append(item)
#             return final_result
#         else:
#             return current_input

#     async def _run_pipe(self, pipe, input, context, add_upstream_outputs = []):
#         # input_dict = {"message": input}
#         # if pipe.do_await:
#         #     # ... await previous execution
#         #     print("input = ", input)
#         #     input = await input
#         # if len(add_upstream_outputs) > 0:
#         #     for upstream_input in add_upstream_outputs:
#         #         outputs = await self.context.get(
#         #             upstream_input["prev_pipe_name"], "output"
#         #         )
#         #         input_dict[upstream_input["input_field"]] = outputs[
#         #             upstream_input["prev_output_field"]
#         #         ]
#         # pipe_input = pipe.input_from_dict(input_dict)
#         # print("pipe_input = ", pipe_input)
#         return pipe.run(input, context) # self.context)

# # class ConfigurationAggregator:
# #     def __init__(self):
# #         self.configs: dict[str, PipeConfig] = {}
# #         self.global_config = {}

# #     def register_pipe(self, pipe: AsyncPipe):
# #         """Register or update a pipe's configuration with default and overridden settings."""
# #         if pipe.config.name in self.configs:
# #             raise ValueError(
# #                 f"Pipe with name {pipe.config.name} already exists."
# #             )
# #         config = copy(pipe.config.dict())
# #         self.configs[config.pop("name")] = config

# #     def get_config(self, pipe_name: str) -> PipeConfig:
# #         """Get the configuration for a specific pipe."""
# #         return self.configs.get(pipe_name, PipeConfig())


# # class Pipeline:
# #     INPUT_TYPE = Type[Any]
# #     OUTPUT_TYPE = Type[Any]

# #     def __init__(
# #         self,
# #         context: Optional[AsyncContext] = None,
# #         config_aggregator: Optional[ConfigurationAggregator] = None,
# #         *args,
# #         **kwargs,
# #     ):
# #         if not config_aggregator:
# #             config_aggregator = ConfigurationAggregator()
# #         if not context:
# #             context = AsyncContext()

# #         self.pipes = []
# #         self.upstream_inputs_mapping = []
# #         self.context = context
# #         self.config_aggregator = config_aggregator
# #         self.flow = PipeFlow.STANDARD

# #     async def add_pipe(
# #         self,
# #         pipe: AsyncPipe,
# #         add_upstream_outputs: Optional[dict] = None,
# #         *args,
# #         **kwargs,
# #     ) -> None:
# #         # if self.pipes and self.pipes[-1].OUTPUT_TYPE != pipe.INPUT_TYPE:
# #         #     raise TypeError(
# #         #         "Output type of the last pipe does not match input type of the new pipe."
# #         #     )
# #         self.pipes.append(pipe)
# #         if not add_upstream_outputs:
# #             add_upstream_outputs = {}
# #         self.upstream_inputs_mapping.append(add_upstream_outputs)
# #         self.config_aggregator.register_pipe(pipe)
# #         await self.context.update(pipe.config.name, {"settings": {}})

# #     async def run(self, input: Any) -> Any:
# #         current_input = input
# #         for pipe, add_upstream_outputs in zip(
# #             self.pipes, self.upstream_inputs_mapping
# #         ):
# #             print("pipe = ", pipe)
# #             print("current_input = ", current_input)
# #             current_input = await self.execute_pipe(
# #                 pipe, current_input, add_upstream_outputs
# #             )
# #             async with self.context.lock:
# #                 print("context = ", self.context.data)
# #         if isinstance(current_input, AsyncGenerator):
# #             print("qqq")
# #             collection = []
# #             async for item in current_input:
# #                 collection.append(item)
# #             return collection
# #         else:
# #             print("zzz")
# #             return await current_input

# #     async def execute_pipe(self, pipe, current_input, add_upstream_outputs):
# #         if self.flow == PipeFlow.FAN_OUT:
# #             if pipe.flow == PipeFlow.STANDARD:
# #                 # Process each item concurrently if the current flow is FAN_OUT
# #                 print("a")
# #                 if hasattr(current_input, "__aiter__"):
# #                     return [
# #                         (
# #                             await self.wrapped_run(
# #                                 item, self.context, add_upstream_outputs
# #                             )
# #                         )
# #                         async for item in current_input
# #                     ]
# #                 else:
# #                     print("b")
# #                     return [
# #                         (
# #                             await self.wrapped_run(
# #                                 item, self.context, add_upstream_outputs
# #                             )
# #                         )
# #                         for item in current_input
# #                     ]
# #             elif pipe.flow == PipeFlow.FAN_IN:
# #                 print("c")
# #                 # Collect the results of the FAN_OUT flow
# #                 self.flow = PipeFlow.STANDARD
# #                 return await self.wrapped_run(
# #                     pipe, current_input, add_upstream_outputs
# #                 )

# #         elif self.flow == PipeFlow.STANDARD:
# #             print("d")
# #             return await self.wrapped_run(
# #                 pipe, current_input, add_upstream_outputs
# #             )
# #         else:
# #             raise ValueError("Invalid flow state.")

# #     async def wrapped_run(self, pipe, input, add_upstream_outputs):
# #         input_dict = {"message": input}
# #         if pipe.do_await:
# #             # ... await previous execution
# #             print("input = ", input)
# #             input = await input
# #         if len(add_upstream_outputs) > 0:
# #             for upstream_input in add_upstream_outputs:
# #                 outputs = await self.context.get(
# #                     upstream_input["prev_pipe_name"], "output"
# #                 )
# #                 input_dict[upstream_input["input_field"]] = outputs[
# #                     upstream_input["prev_output_field"]
# #                 ]
# #         pipe_input = pipe.input_from_dict(input_dict)
# #         return pipe.run(pipe_input, self.context)
