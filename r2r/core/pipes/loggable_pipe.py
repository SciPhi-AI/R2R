import asyncio
import uuid
from abc import abstractmethod
from typing import Any, AsyncGenerator, Optional

from ..logging.kv_logger import KVLoggingSingleton
from ..logging.run_manager import RunManager, manage_run
from .base_pipe import AsyncPipe, AsyncState, PipeType


class LoggableAsyncPipe(AsyncPipe):
    """An asynchronous pipe for processing data with logging capabilities."""

    class PipeConfig(AsyncPipe.PipeConfig):
        """Configuration for a loggable pipe."""

        name: str = "default_loggable_pipe"
        max_log_queue_size: int = 100

    def __init__(
        self,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        config: Optional[AsyncPipe.PipeConfig] = None,
        run_manager: Optional[RunManager] = None,
        *args,
        **kwargs,
    ):
        if not pipe_logger:
            pipe_logger = KVLoggingSingleton()
        self.pipe_logger = pipe_logger
        self.log_queue = asyncio.Queue()
        self.log_worker_task = None
        self._run_manager = run_manager or RunManager(pipe_logger)
        super().__init__(type=type, config=config, *args, **kwargs)

    async def log_worker(self):
        while True:
            log_data = await self.log_queue.get()
            run_id, key, value = log_data
            await self.pipe_logger.log(run_id, key, value)
            self.log_queue.task_done()

    async def enqueue_log(self, run_id: uuid.UUID, key: str, value: str):
        if self.log_queue.qsize() < self.config.max_log_queue_size:
            await self.log_queue.put((run_id, key, value))

    async def run(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
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
                        input, state, run_id=run_id, *args, **kwargs
                    ):
                        yield result
                finally:
                    await self.log_queue.join()
                    self.log_worker_task.cancel()
                    self.log_queue = asyncio.Queue()

        return wrapped_run()

    @abstractmethod
    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        pass
