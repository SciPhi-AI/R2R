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
    AGGREGATE = "aggregate"
    GENERATION = "generation"
    TRANSFORM = "transform"
    SEARCH = "search"
    OTHER = "other"


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
        flow: PipeFlow = PipeFlow.STANDARD,
        type: PipeType = PipeType.OTHER,
        config: Optional[PipeConfig] = None,
    ):
        self._flow = flow
        self._type = type
        self._config = config or self.Config()

    @property
    def flow(self) -> PipeFlow:
        return self._flow

    @property
    def type(self) -> PipeType:
        return self._type

    @property
    def config(self) -> PipeConfig:
        return self._config

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
        self.futures = {}
        self.level = 0

    async def add_pipe(
        self,
        pipe: AsyncPipe,
        add_upstream_outputs: Optional[list[dict[str, str]]] = None,
        *args,
        **kwargs,
    ) -> None:
        self.futures[pipe.config.name] = asyncio.Future()
        self.pipes.append(pipe)
        if not add_upstream_outputs:
            add_upstream_outputs = []
        self.upstream_outputs.append(add_upstream_outputs)
        await self.context.update(pipe.config.name, {"settings": {}})

    async def run(self, input):
        current_input = input
        for pipe_num in range(len(self.pipes)):
            if self.pipes[pipe_num].flow == PipeFlow.FAN_OUT:
                if self.level == 0:
                    current_input = await self._run_pipe(
                        pipe_num, current_input
                    )
                    self.level += 1
                elif self.level == 1:
                    raise ValueError("Fan out not supported at level 1")
            elif self.pipes[pipe_num].flow == PipeFlow.STANDARD:
                if self.level == 0:
                    current_input = await self._run_pipe(
                        pipe_num, current_input
                    )
                elif self.level == 1:
                    current_input = [
                        await self._run_pipe(pipe_num, item)
                        async for item in current_input
                    ]
            elif self.pipes[pipe_num].flow == PipeFlow.FAN_IN:
                if self.level == 0:
                    raise ValueError("Fan in not supported at level 0")
                if self.level == 1:
                    current_input = await self._run_pipe(
                        pipe_num, current_input
                    )
                    self.level -= 1
            self.futures[self.pipes[pipe_num].config.name].set_result(
                current_input
            )

        if inspect.isasyncgen(current_input):
            final_result = []
            async for item in current_input:
                final_result.append(item)
            return final_result
        else:
            return await current_input

    async def _run_pipe(self, pipe_num, input):
        # Collect inputs, waiting for the necessary futures
        pipe = self.pipes[pipe_num]
        add_upstream_outputs = self.upstream_outputs[pipe_num]
        input_dict = {"message": input}

        for upstream_input in add_upstream_outputs:
            upstream_pipe_name = upstream_input["prev_pipe_name"]

            async def resolve_future_output(future):
                result = future.result()
                # consume the async generator
                return [item async for item in result]

            async def replay_items_as_async_gen(items):
                for item in items:
                    yield item

            temp_results = await resolve_future_output(
                self.futures[upstream_pipe_name]
            )
            if upstream_pipe_name == self.pipes[pipe_num - 1].config.name:
                input_dict["message"] = replay_items_as_async_gen(temp_results)

            outputs = await self.context.get(
                upstream_input["prev_pipe_name"], "output"
            )
            input_dict[upstream_input["input_field"]] = outputs[
                upstream_input["prev_output_field"]
            ]

        print("executing input_dict = ", input_dict)
        # Execute the pipe with all inputs resolved
        return await pipe.run(pipe.Input(**input_dict), self.context)


class PipeConfig:
    pass
