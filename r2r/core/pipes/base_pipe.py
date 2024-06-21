import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PipeType(Enum):
    INGESTOR = "ingestor"
    EVAL = "eval"
    GENERATOR = "generator"
    SEARCH = "search"
    TRANSFORM = "transform"
    OTHER = "other"


class AsyncState:
    """A state object for storing data between pipes."""

    def __init__(self):
        self.data = {}
        self.lock = asyncio.Lock()

    async def update(self, outer_key: str, values: dict):
        """Update the state with new values."""
        async with self.lock:
            if not isinstance(values, dict):
                raise ValueError("Values must be contained in a dictionary.")
            if outer_key not in self.data:
                self.data[outer_key] = {}
            for inner_key, inner_value in values.items():
                self.data[outer_key][inner_key] = inner_value

    async def get(self, outer_key: str, inner_key: str, default=None):
        """Get a value from the state."""
        async with self.lock:
            if outer_key not in self.data:
                raise ValueError(
                    f"Key {outer_key} does not exist in the state."
                )
            if inner_key not in self.data[outer_key]:
                return default or {}
            return self.data[outer_key][inner_key]

    async def delete(self, outer_key: str, inner_key: Optional[str] = None):
        """Delete a value from the state."""
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
    """An asynchronous pipe for processing data."""

    class PipeConfig(BaseModel):
        """Configuration for a pipe."""

        name: str = "default_pipe"

        class Config:
            extra = "forbid"
            arbitrary_types_allowed = True

    class Input(BaseModel):
        """Input for a pipe."""

        message: AsyncGenerator[Any, None]

        class Config:
            extra = "forbid"
            arbitrary_types_allowed = True

    def __init__(
        self,
        type: PipeType = PipeType.OTHER,
        config: Optional[PipeConfig] = None,
    ):
        self._config = config or self.PipeConfig()
        self._run_info = None
        self._type = type

        logger.debug(
            f"Initialized pipe {self.config.name} of type {self.type}"
        )

    @property
    def config(self) -> PipeConfig:
        return self._config

    @property
    def type(self) -> PipeType:
        return self._type

    async def run(
        self,
        input: Input,
        state: AsyncState,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        result = self._run_logic(input, state)
        return result

    @abstractmethod
    async def _run_logic(
        self, input: Input, state: AsyncState, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        pass
