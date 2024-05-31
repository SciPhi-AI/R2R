import contextvars
import uuid
from contextlib import asynccontextmanager
from typing import Any

from .kv_logger import KVLoggingSingleton

run_id_var = contextvars.ContextVar("run_id", default=None)


class RunManager:
    def __init__(self, logger: KVLoggingSingleton):
        self.logger = logger
        self.run_info = {}

    def generate_run_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def set_run_info(self, pipeline_type: str):
        run_id = run_id_var.get()
        if run_id is None:
            run_id = self.generate_run_id()
            token = run_id_var.set(run_id)
            self.run_info[run_id] = {"pipeline_type": pipeline_type}
        else:
            token = run_id_var.set(run_id)
        return run_id, token

    async def get_run_info(self):
        run_id = run_id_var.get()
        return self.run_info.get(run_id, None)

    async def log_run_info(
        self, key: str, value: Any, is_info_log: bool = False
    ):
        run_id = run_id_var.get()
        if run_id:
            await self.logger.log(
                log_id=run_id, key=key, value=value, is_info_log=is_info_log
            )

    async def clear_run_info(self, token: contextvars.Token):
        run_id = run_id_var.get()
        run_id_var.reset(token)
        if run_id and run_id in self.run_info:
            del self.run_info[run_id]


@asynccontextmanager
async def manage_run(run_manager: RunManager, pipeline_type: str):
    run_id, token = await run_manager.set_run_info(pipeline_type)
    try:
        yield run_id
    finally:
        # Note: Do not clear the run info to ensure the run ID remains the same
        run_id_var.reset(token)
