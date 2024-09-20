import asyncio
import inspect
import json
from typing import AsyncGenerator, Generator

import httpx
import nest_asyncio
from fastapi.testclient import TestClient

from .auth import AuthMethods
from .ingestion import IngestionMethods
from .management import ManagementMethods
from .models import R2RException
from .restructure import RestructureMethods
from .retrieval import RetrievalMethods
from .server import ServerMethods

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
        base_url: str = "http://localhost:7272",
        prefix: str = "/v2",
        custom_client=None,
        timeout: float = 300.0,
    ):
        self.base_url = base_url
        self.prefix = prefix
        self.access_token = None
        self._refresh_token = None
        self.client = custom_client or httpx.AsyncClient(timeout=timeout)
        self.timeout = timeout

        # Initialize methods grouop
        self._auth = AuthMethods
        self._ingestion = IngestionMethods
        self._management = ManagementMethods
        self._restructure = RestructureMethods
        self._retrieval = RetrievalMethods
        self._server = ServerMethods

        # Collect all methods from the methods group
        self._methods = {}
        for collection in [
            self._auth,
            self._ingestion,
            self._management,
            self._restructure,
            self._retrieval,
            self._server,
        ]:
            for name, method in inspect.getmembers(
                collection, predicate=inspect.isfunction
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
        if (
            kwargs.get("params", None) == {}
            or kwargs.get("params", None) is None
        ):
            if "params" in kwargs:
                kwargs.pop("params")

        if isinstance(self.client, TestClient):
            # Weird mocking fix...
            params = kwargs.pop("params", {})
            params = {**params, **EMPTY_ARGS}

            response = getattr(self.client, method.lower())(
                url, headers=headers, params=params, **kwargs
            )
            return response.json() if response.content else None
        else:
            try:
                response = await self.client.request(
                    method, url, headers=headers, **kwargs
                )
                await handle_request_error_async(response)
                return response.json() if response.content else None
            except httpx.RequestError as e:
                raise R2RException(
                    status_code=500, message=f"Request failed: {str(e)}"
                ) from e

    async def _make_streaming_request(
        self, method: str, endpoint: str, **kwargs
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}{self.prefix}/{endpoint}"
        headers = kwargs.pop("headers", {})
        if self.access_token and endpoint not in [
            "register",
            "login",
            "verify_email",
        ]:
            headers.update(self._get_auth_header())

        async with httpx.AsyncClient() as client:
            async with client.stream(
                method, url, headers=headers, timeout=self.timeout, **kwargs
            ) as response:
                handle_request_error(response)
                async for chunk in response.aiter_text():
                    yield chunk

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

    def _sync_generator(self, async_gen: AsyncGenerator) -> Generator:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while True:
                yield loop.run_until_complete(async_gen.__anext__())
        except StopAsyncIteration:
            pass
        finally:
            loop.close()

    def __getattr__(self, name):
        async_attr = getattr(self.async_client, name)
        if callable(async_attr):

            def sync_wrapper(*args, **kwargs):
                result = asyncio.get_event_loop().run_until_complete(
                    async_attr(*args, **kwargs)
                )
                if isinstance(result, AsyncGenerator):
                    return self._sync_generator(result)
                return result

            return sync_wrapper
        return async_attr

    def __dir__(self):
        return dir(self.async_client)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.get_event_loop().run_until_complete(self.async_client.close())
