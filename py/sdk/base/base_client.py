import asyncio
import contextlib
from functools import wraps
from typing import Optional

from shared.abstractions import R2RException


def sync_wrapper(async_func):
    """Decorator to convert async methods to sync methods"""

    @wraps(async_func)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(async_func(*args, **kwargs))

    return wrapper


def sync_generator_wrapper(async_gen_func):
    """Decorator to convert async generators to sync generators"""

    @wraps(async_gen_func)
    def wrapper(*args, **kwargs):
        async_gen = async_gen_func(*args, **kwargs)
        loop = asyncio.get_event_loop()
        with contextlib.suppress(StopAsyncIteration):
            while True:
                yield loop.run_until_complete(async_gen.__anext__())

    return wrapper


class BaseClient:
    def __init__(
        self,
        base_url: str = "http://localhost:7272",
        prefix: str = "/v2",
        timeout: float = 300.0,
    ):
        self.base_url = base_url
        self.prefix = prefix
        self.timeout = timeout
        self.access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None

    def _get_auth_header(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def _ensure_authenticated(self):
        if not self.access_token:
            raise R2RException(
                status_code=401,
                message="Not authenticated. Please login first.",
            )

    def _get_full_url(self, endpoint: str, version: str = "v2") -> str:
        return f"{self.base_url}/{version}/{endpoint}"

    def _prepare_request_args(self, endpoint: str, **kwargs) -> dict:
        headers = kwargs.pop("headers", {})
        if self.access_token and endpoint not in [
            "register",
            "login",
            "verify_email",
        ]:
            headers.update(self._get_auth_header())
        if (
            kwargs.get("params", None) == {}
            or kwargs.get("params", None) is None
        ):
            kwargs.pop("params", None)

        return {"headers": headers, **kwargs}
