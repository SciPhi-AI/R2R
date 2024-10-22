import json
from typing import Any, AsyncGenerator

import httpx

from shared.abstractions import R2RException

from .base.base_client import BaseClient
from .mixins import (
    AuthMixins,
    IngestionMixins,
    KGMixins,
    ManagementMixins,
    RetrievalMixins,
    ServerMixins,
)


class R2RAsyncClient(
    BaseClient,
    AuthMixins,
    IngestionMixins,
    KGMixins,
    ManagementMixins,
    RetrievalMixins,
    ServerMixins,
):
    """
    Asynchronous client for interacting with the R2R API.

    Args:
        base_url (str, optional): The base URL of the R2R API. Defaults to "http://localhost:7272".
        prefix (str, optional): The prefix for the API. Defaults to "/v2".
        custom_client (httpx.AsyncClient, optional): A custom HTTP client. Defaults to None.
        timeout (float, optional): The timeout for requests. Defaults to 300.0.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:7272",
        prefix: str = "/v2",
        custom_client=None,
        timeout: float = 300.0,
    ):
        super().__init__(base_url, prefix, timeout)
        self.client = custom_client or httpx.AsyncClient(timeout=timeout)

    async def _make_request(self, method: str, endpoint: str, **kwargs):
        url = self._get_full_url(endpoint)
        request_args = self._prepare_request_args(endpoint, **kwargs)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, **request_args)
                await self._handle_response(response)
                return response.json() if response.content else None
        except httpx.RequestError as e:
            raise R2RException(
                status_code=500, message=f"Request failed: {str(e)}"
            ) from e

    async def _make_streaming_request(
        self, method: str, endpoint: str, **kwargs
    ) -> AsyncGenerator[Any, None]:
        url = self._get_full_url(endpoint)
        request_args = self._prepare_request_args(endpoint, **kwargs)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(method, url, **request_args) as response:
                await self._handle_response(response)
                async for line in response.aiter_lines():
                    if line.strip():  # Ignore empty lines
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            yield line

    async def _handle_response(self, response):
        if response.status_code >= 400:
            try:
                error_content = response.json()
                if isinstance(error_content, dict):
                    message = error_content.get("detail", {}).get(
                        "message", str(error_content)
                    ) if isinstance(error_content.get("detail"), dict) else error_content.get("detail", str(error_content))
                else:
                    message = str(error_content)
            except json.JSONDecodeError:
                message = response.text

            raise R2RException(
                status_code=response.status_code, 
                message=message
            )

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
