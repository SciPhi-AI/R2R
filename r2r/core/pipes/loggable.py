import asyncio
import uuid
from typing import Any, AsyncGenerator, Optional

from .base import AsyncPipe, AsyncState, PipeType
from .logging import PipeLoggingConnectionSingleton


class LoggableAsyncPipe(AsyncPipe):
    class PipeConfig(AsyncPipe.PipeConfig):
        name: str = "default_loggable_pipe"
        max_log_queue_size: int = 100

    def __init__(
        self,
        pipe_logger: Optional[PipeLoggingConnectionSingleton] = None,
        type: PipeType = PipeType.OTHER,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs
    ):
        if not pipe_logger:
            pipe_logger = PipeLoggingConnectionSingleton()
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
    ) -> AsyncGenerator[Any, None]:
        async def wrapped_run() -> AsyncGenerator[Any, None]:
            await self._initiate_run(run_id)
            self.log_worker_task = asyncio.create_task(self.log_worker())
            try:
                async for result in self._run_logic(input, state):
                    yield result
            finally:
                await self.log_queue.join()
                self.log_worker_task.cancel()

        return wrapped_run()
