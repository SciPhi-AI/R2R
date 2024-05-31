import asyncio
import uuid
from typing import Any, AsyncGenerator, Optional

from .base_pipe import AsyncPipe, AsyncState, PipeType, manage_run_info
from .pipe_logging import KVLoggingConnectionSingleton


class LoggableAsyncPipe(AsyncPipe):
    """An asynchronous pipe for processing data with logging capabilities."""

    class PipeConfig(AsyncPipe.PipeConfig):
        """Configuration for a loggable pipe."""

        name: str = "default_loggable_pipe"
        max_log_queue_size: int = 100

    def __init__(
        self,
        pipe_logger: Optional[KVLoggingConnectionSingleton] = None,
        type: PipeType = PipeType.OTHER,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        if not pipe_logger:
            pipe_logger = KVLoggingConnectionSingleton()
        self.pipe_logger = pipe_logger
        self.log_queue = asyncio.Queue()
        self.log_worker_task = None

        super().__init__(type=type, config=config, *args, **kwargs)

    async def log_worker(self):
        while True:
            log_data = await self.log_queue.get()
            pipe_run_id, key, value = log_data
            await self.pipe_logger.log(pipe_run_id, key, value)
            self.log_queue.task_done()

    async def enqueue_log(self, pipe_run_id: str, key: str, value: str):
        if self.log_queue.qsize() < self.config.max_log_queue_size:
            await self.log_queue.put((pipe_run_id, key, value))

    async def run(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: Optional[uuid.UUID] = None,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        """Run the pipe with logging capabilities."""

        async def wrapped_run() -> AsyncGenerator[Any, None]:
            async with manage_run_info(self, run_id):
                self.log_worker_task = asyncio.create_task(
                    self.log_worker(), name=f"log-worker-{self.config.name}"
                )
                try:
                    async for result in self._run_logic(
                        input, state, *args, **kwargs
                    ):
                        yield result
                finally:
                    await self.log_queue.join()
                    self.log_worker_task.cancel()
                    self.log_queue = asyncio.Queue()

        return wrapped_run()
