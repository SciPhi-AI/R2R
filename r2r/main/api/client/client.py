import asyncio
import inspect
import json

import httpx
import nest_asyncio
from fastapi.testclient import TestClient

from r2r.base import R2RException

# Import the new client modules
from .auth import AuthMethods
from .ingestion import IngestionMethods
from .management import ManagementMethods
from .restructure import RestructureMethods
from .retrieval import RetrievalMethods

nest_asyncio.apply()

# The empty args become necessary after a recent modification to `base_endpoint`
# TODO - Remove the explicitly empty args
EMPTY_ARGS = {"args": "", "kwargs": "{}"}


def handle_request_error(response):
    if response.status_code < 400:
        return

    try:
        error_content = response.json()
        if isinstance(error_content, dict) and "detail" in error_content:
            detail = error_content["detail"]
            if isinstance(detail, dict):
                message = detail.get("message", str(response.text))
            else:
                message = str(detail)
        else:
            message = str(error_content)
    except json.JSONDecodeError:
        message = response.text

    raise R2RException(
        status_code=response.status_code,
        message=message,
    )


async def handle_request_error_async(response):
    if response.status_code < 400:
        return

    try:
        if response.headers.get("content-type") == "application/json":
            error_content = await response.json()
        else:
            error_content = await response.text

        if isinstance(error_content, dict) and "detail" in error_content:
            detail = error_content["detail"]
            if isinstance(detail, dict):
                message = detail.get("message", str(error_content))
            else:
                message = str(detail)
        else:
            message = str(error_content)
    except Exception:
        message = response.text

    raise R2RException(
        status_code=response.status_code,
        message=message,
    )


class R2RAsyncClient:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        prefix: str = "/v1",
        custom_client=None,
        timeout: float = 60.0,
    ):
        self.base_url = base_url
        self.prefix = prefix
        self.access_token = None
        self._refresh_token = None
        self.client = custom_client or httpx.AsyncClient(timeout=timeout)
        self.timeout = timeout

        # Initialize method groups
        self._auth = AuthMethods
        self._retrieval = RetrievalMethods
        self._ingestion = IngestionMethods
        self._restructure = RestructureMethods
        self._management = ManagementMethods

        # Collect all methods from the method groups
        self._methods = {}
        for group in [
            self._auth,
            self._retrieval,
            self._ingestion,
            self._restructure,
            self._management,
        ]:
            for name, method in inspect.getmembers(
                group, predicate=inspect.isfunction
            ):
                if not name.startswith("_"):
                    self._methods[name] = method

    async def _make_request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{self.prefix}/{endpoint}"
        headers = kwargs.pop("headers", {})
        if self.access_token and endpoint not in [
            "register",
            "login",
            "verify_email",
        ]:
            headers.update(self._get_auth_header())
        params = kwargs.pop("params", {})
        params = {**params, **EMPTY_ARGS}

        if isinstance(self.client, TestClient):
            response = getattr(self.client, method.lower())(
                url, headers=headers, params=params, **kwargs
            )
            return response.json()
        else:
            try:
                response = await self.client.request(
                    method, url, headers=headers, params=params, **kwargs
                )
                await handle_request_error_async(response)
                return response.json()
            except httpx.RequestError as e:
                raise R2RException(
                    status_code=500, message=f"Request failed: {str(e)}"
                )

    def _get_auth_header(self) -> dict:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def _ensure_authenticated(self):
        if not self.access_token:
            raise R2RException(
                status_code=401,
                message="Not authenticated. Please login first.",
            )

    async def health(self) -> dict:
        return await self._make_request("GET", "health")

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __getattr__(self, name):
        if name in self._methods:
            return lambda *args, **kwargs: self._methods[name](
                self, *args, **kwargs
            )
        raise AttributeError(f"'R2RClient' object has no attribute '{name}'")

    def __dir__(self):
        return list(set(super().__dir__() + list(self._methods.keys())))


class R2RClient:
    def __init__(self, *args, **kwargs):
        self.async_client = R2RAsyncClient(*args, **kwargs)

    def __getattr__(self, name):
        async_attr = getattr(self.async_client, name)
        if callable(async_attr):

            def sync_wrapper(*args, **kwargs):
                return asyncio.get_event_loop().run_until_complete(
                    async_attr(*args, **kwargs)
                )

            return sync_wrapper
        return async_attr

    def __dir__(self):
        return dir(self.async_client)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.get_event_loop().run_until_complete(self.async_client.close())
