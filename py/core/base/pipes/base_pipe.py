import asyncio
import logging
from abc import abstractmethod
from enum import Enum
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from pydantic import BaseModel

from core.base.logging.run_logger import RunLoggingSingleton
from core.base.logging.run_manager import RunManager, manage_run

logger = logging.getLogger(__name__)


class PipeType(Enum):
    INGESTOR = "ingestor"
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


class AsyncPipe:
    """An asynchronous pipe for processing data with logging capabilities."""

    class PipeConfig(BaseModel):
        """Configuration for a pipe."""

        name: str = "default_pipe"
        max_log_queue_size: int = 100

        class Config:
            extra = "forbid"
            arbitrary_types_allowed = True

    class Input(BaseModel):
        """Input for a pipe."""

        message: Any

        class Config:
            extra = "forbid"
            arbitrary_types_allowed = True

    def __init__(
        self,
        type: PipeType = PipeType.OTHER,
        config: Optional[PipeConfig] = None,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        run_manager: Optional[RunManager] = None,
    ):
        self._config = config or self.PipeConfig()
        self._type = type
        self.pipe_logger = pipe_logger or RunLoggingSingleton()
        self.log_queue = asyncio.Queue()
        self.log_worker_task = None
        self._run_manager = run_manager or RunManager(self.pipe_logger)

        logger.debug(
            f"Initialized pipe {self.config.name} of type {self.type}"
        )

    @property
    def config(self) -> PipeConfig:
        return self._config

    @property
    def type(self) -> PipeType:
        return self._type

    async def log_worker(self):
        while True:
            log_data = await self.log_queue.get()
            run_id, key, value = log_data
            await self.pipe_logger.log(run_id, key, value)
            self.log_queue.task_done()

    async def enqueue_log(self, run_id: UUID, key: str, value: str):
        if self.log_queue.qsize() < self.config.max_log_queue_size:
            await self.log_queue.put((run_id, key, value))

    async def run(
        self,
        input: Input,
        state: Optional[AsyncState] = None,
        run_manager: Optional[RunManager] = None,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        """Run the pipe with logging capabilities."""

        run_manager = run_manager or self._run_manager

        async def wrapped_run() -> AsyncGenerator[Any, None]:
            async with manage_run(run_manager, self.config.name) as run_id:
                self.log_worker_task = asyncio.create_task(
                    self.log_worker(), name=f"log-worker-{self.config.name}"
                )
                try:
                    async for result in self._run_logic(
                        input, state=state, run_id=run_id, *args, **kwargs
                    ):
                        yield result
                finally:
                    # Ensure the log queue is empty
                    while not self.log_queue.empty():
                        await self.log_queue.get()
                        self.log_queue.task_done()

                    # Cancel and wait for the log worker task
                    if (
                        self.log_worker_task
                        and not self.log_worker_task.done()
                    ):
                        self.log_worker_task.cancel()
                        try:
                            await self.log_worker_task
                        except asyncio.CancelledError:
                            pass

        return wrapped_run()

    @abstractmethod
    async def _run_logic(
        self,
        input: Input,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        pass
