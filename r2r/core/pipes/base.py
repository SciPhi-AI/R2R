import asyncio
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

from ..utils import generate_run_id


class PipeFlow(Enum):
    STANDARD = "standard"
    FAN_OUT = "fan_out"
    FAN_IN = "fan_in"


class PipeType(Enum):
    COLLECTOR = "collector"
    GENERATOR = "generator"
    INGESTOR = "ingestor"
    TRANSFORM = "transformer"
    SEARCH = "search"
    OTHER = "other"


class PipeRunInfo(BaseModel):
    run_id: uuid.UUID


class AsyncState:
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
                    f"Key {outer_key} does not exist in the state."
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
                        f"Key {inner_key} does not exist in the state."
                    )
                del self.data[outer_key][inner_key]


class AsyncPipe(ABC):
    class PipeConfig(BaseModel):
        name: str = "default_pipe"

        class Config:
            extra = "forbid"
            arbitrary_types_allowed = True

    class Input(BaseModel):
        message: AsyncGenerator[Any, None]

        class Config:
            extra = "forbid"
            arbitrary_types_allowed = True

    def __init__(
        self,
        flow: PipeFlow = PipeFlow.STANDARD,
        type: PipeType = PipeType.OTHER,
        config: Optional[PipeConfig] = None,
    ):
        self._config = config or self.PipeConfig()
        self._flow = flow
        self._run_info = None
        self._type = type

    @property
    def flow(self) -> PipeFlow:
        return self._flow

    @property
    def config(self) -> PipeConfig:
        return self._config

    @property
    def type(self) -> PipeType:
        return self._type

    @property
    def run_info(self) -> PipeRunInfo:
        return self._run_info

    async def run(
        self,
        input: Input,
        state: AsyncState,
        run_id: Optional[uuid.UUID] = None,
    ) -> AsyncGenerator[Any, None]:
        await self._initiate_run(run_id)
        result = self._run_logic(input, state)
        return result

    @abstractmethod
    async def _run_logic(
        self, input: Input, state: AsyncState
    ) -> AsyncGenerator[Any, None]:
        pass

    async def _initiate_run(self, run_id: Optional[uuid.UUID] = None):
        if not run_id:
            run_id = generate_run_id()
        self._run_info = PipeRunInfo(run_id=run_id)
