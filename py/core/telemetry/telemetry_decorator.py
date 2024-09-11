import asyncio
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from pathlib import Path

import toml

from core.telemetry.events import ErrorEvent, FeatureUsageEvent
from core.telemetry.posthog import telemetry_client

logger = logging.getLogger(__name__)


class ProductTelemetryClient:
    USER_ID_PATH = str(Path.home() / ".cache" / "r2r" / "telemetry_user_id")
    UNKNOWN_USER_ID = "UNKNOWN"
    _curr_user_id = None
    _version = None

    @property
    def version(self) -> str:
        if self._version is None:
            try:
                pyproject_path = (
                    Path(__file__).parent.parent.parent / "pyproject.toml"
                )
                pyproject_data = toml.load(pyproject_path)
                self._version = pyproject_data["tool"]["poetry"]["version"]
            except Exception as e:
                logger.error(
                    f"Error reading version from pyproject.toml: {str(e)}"
                )
                self._version = "UNKNOWN"
        return self._version

    @property
    def user_id(self) -> str:
        if self._curr_user_id:
            return self._curr_user_id

        try:
            if not os.path.exists(self.USER_ID_PATH):
                os.makedirs(os.path.dirname(self.USER_ID_PATH), exist_ok=True)
                with open(self.USER_ID_PATH, "w") as f:
                    new_user_id = str(uuid.uuid4())
                    f.write(new_user_id)
                self._curr_user_id = new_user_id
            else:
                with open(self.USER_ID_PATH, "r") as f:
                    self._curr_user_id = f.read().strip()
        except Exception:
            self._curr_user_id = self.UNKNOWN_USER_ID
        return self._curr_user_id


product_telemetry_client = ProductTelemetryClient()


def get_project_metadata():
    import platform

    return {
        "os": platform.system(),
        "python_version": platform.python_version(),
        "version": product_telemetry_client.version,
    }


# Create a thread pool with a fixed number of workers
telemetry_thread_pool = ThreadPoolExecutor(max_workers=2)


def telemetry_event(event_name):
    def decorator(func):
        def log_telemetry(event_type, user_id, metadata, error_message=None):
            try:
                if event_type == "feature":
                    telemetry_client.capture(
                        FeatureUsageEvent(
                            user_id=user_id,
                            properties=metadata,
                            feature=event_name,
                        )
                    )
                elif event_type == "error":
                    telemetry_client.capture(
                        ErrorEvent(
                            user_id=user_id,
                            properties=metadata,
                            endpoint=event_name,
                            error_message=error_message,
                        )
                    )
            except Exception as e:
                logger.error(f"Error in telemetry event logging: {str(e)}")

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            metadata = get_project_metadata()
            user_id = product_telemetry_client.user_id

            try:
                result = await func(*args, **kwargs)
                telemetry_thread_pool.submit(
                    log_telemetry, "feature", user_id, metadata
                )
                return result
            except Exception as e:
                telemetry_thread_pool.submit(
                    log_telemetry, "error", user_id, metadata, str(e)
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    async_wrapper(*args, **kwargs), loop
                )
                return future.result()
            else:
                return loop.run_until_complete(async_wrapper(*args, **kwargs))

        return (
            async_wrapper
            if asyncio.iscoroutinefunction(func)
            else sync_wrapper
        )

    return decorator
