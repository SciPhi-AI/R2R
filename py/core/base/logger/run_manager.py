import asyncio
import contextvars
from contextlib import asynccontextmanager
from typing import Optional
from uuid import UUID

from core.base.api.models import User
from core.base.utils import generate_id

run_id_var = contextvars.ContextVar("run_id", default=generate_id())


class RunManager:
    def __init__(self):
        self.run_info: dict[UUID, dict] = {}

    async def set_run_info(self, run_id: Optional[UUID] = None):
        run_id = run_id or run_id_var.get()
        if run_id is None:
            run_id = generate_id()
            token = run_id_var.set(run_id)
        else:
            token = run_id_var.set(run_id)
        return run_id, token

    async def get_info_logs(self):
        run_id = run_id_var.get()
        return self.run_info.get(run_id, None)

    async def log_run_info(
        self,
        user: User,
    ):
        if asyncio.iscoroutine(user):
            user = await user

    async def clear_run_info(self, token: contextvars.Token):
        run_id = run_id_var.get()
        run_id_var.reset(token)
        if run_id and run_id in self.run_info:
            del self.run_info[run_id]


@asynccontextmanager
async def manage_run(
    run_manager: RunManager,
    run_id: Optional[UUID] = None,
):
    run_id, token = await run_manager.set_run_info(run_id)
    try:
        yield run_id
    finally:
        # Check if we're in a test environment
        if isinstance(token, contextvars.Token):
            run_id_var.reset(token)
        else:
            # We're in a test environment, just reset the run_id_var
            run_id_var.set(None)  # type: ignore
