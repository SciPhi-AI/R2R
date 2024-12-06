import asyncio
import contextlib
import logging
from pathlib import Path

import aiofiles
from fastapi import WebSocket
from fastapi.requests import Request
from fastapi.templating import Jinja2Templates

from core.base.logger.base import RunType
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from .base_router import BaseRouterV3


class LogsRouter(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: (
            HatchetOrchestrationProvider | SimpleOrchestrationProvider
        ),
        run_type: RunType = RunType.UNSPECIFIED,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)
        CURRENT_DIR = Path(__file__).resolve().parent
        TEMPLATES_DIR = CURRENT_DIR.parent / "templates"
        self.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
        self.services = services
        self.log_file = Path.cwd() / "logs" / "app.log"
        self.log_file.parent.mkdir(exist_ok=True)
        if not self.log_file.exists():
            self.log_file.touch(mode=0o666)

        # Start from the beginning of the file
        self.last_position = 0

    async def read_full_file(self) -> str:
        """Read the entire log file from the start."""
        if not self.log_file.exists():
            return "Initializing logging system..."

        try:
            async with aiofiles.open(self.log_file, mode="r") as f:
                # Start at beginning
                await f.seek(0)
                full_content = await f.read()
                # Move last_position to end of file after reading full content
                self.last_position = await f.tell()
                return full_content
        except Exception as e:
            logging.error(f"Error reading full logs: {str(e)}")
            return f"Error accessing full log file: {str(e)}"

    async def read_new_logs(self) -> str:
        """Read new logs appended after last_position."""
        if not self.log_file.exists():
            return "Initializing logging system..."

        try:
            async with aiofiles.open(self.log_file, mode="r") as f:
                await f.seek(self.last_position)
                new_content = await f.read()
                self.last_position = await f.tell()
                return new_content or ""
        except Exception as e:
            logging.error(f"Error reading logs: {str(e)}")
            return f"Error accessing log file: {str(e)}"

    def _setup_routes(self):
        @self.router.websocket("/logs/stream")
        async def stream_logs(websocket: WebSocket):
            await websocket.accept()
            try:
                # Send the entire file content upon initial connection
                full_logs = await self.read_full_file()
                if full_logs:
                    await websocket.send_text(full_logs)

                # Now send incremental updates only
                while True:
                    new_logs = await self.read_new_logs()
                    if new_logs:
                        await websocket.send_text(new_logs)
                    await asyncio.sleep(0.5)
            except Exception as e:
                logging.error(f"WebSocket error: {str(e)}")
            finally:
                with contextlib.suppress(Exception):
                    await websocket.close()

        @self.router.get("/logs/viewer")
        async def get_log_viewer(request: Request):
            return self.templates.TemplateResponse(
                "log_viewer.html", {"request": request}
            )
