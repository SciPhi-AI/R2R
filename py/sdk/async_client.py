import json
from io import BytesIO
from typing import Any, AsyncGenerator

import httpx

from shared.abstractions import R2RException

from .asnyc_methods import (
    ChunksSDK,
    CollectionsSDK,
    ConversationsSDK,
    DocumentsSDK,
    GraphsSDK,
    IndicesSDK,
    PromptsSDK,
    RetrievalSDK,
    SystemSDK,
    UsersSDK,
)
from .base.base_client import BaseClient


class R2RAsyncClient(BaseClient):
    """Asynchronous client for interacting with the R2R API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 300.0,
        custom_client=None,
    ):
        super().__init__(base_url, timeout)
        self.client = custom_client or httpx.AsyncClient(timeout=timeout)
        self.chunks = ChunksSDK(self)
        self.collections = CollectionsSDK(self)
        self.conversations = ConversationsSDK(self)
        self.documents = DocumentsSDK(self)
        self.graphs = GraphsSDK(self)
        self.indices = IndicesSDK(self)
        self.prompts = PromptsSDK(self)
        self.retrieval = RetrievalSDK(self)
        self.system = SystemSDK(self)
        self.users = UsersSDK(self)

    async def _make_request(
        self, method: str, endpoint: str, version: str = "v3", **kwargs
    ):
        url = self._get_full_url(endpoint, version)
        if (
            "https://api.sciphi.ai" in url
            and ("login" not in endpoint)
            and ("create" not in endpoint)
            and ("users" not in endpoint)
            and ("health" not in endpoint)
            and (not self.access_token and not self.api_key)
        ):
            raise R2RException(
                status_code=401,
                message="Access token or api key is required to access `https://api.sciphi.ai`. To change the base url, use `set_base_url` method or set the local environment variable `R2R_API_BASE` to `http://localhost:7272`.",
            )
        request_args = self._prepare_request_args(endpoint, **kwargs)

        try:
            response = await self.client.request(method, url, **request_args)
            await self._handle_response(response)
            if "application/json" in response.headers.get("Content-Type", ""):
                return response.json() if response.content else None
            else:
                return BytesIO(response.content)

        except httpx.RequestError as e:
            raise R2RException(
                status_code=500,
                message=f"Request failed: {str(e)}",
            ) from e

    async def _make_streaming_request(
        self, method: str, endpoint: str, version: str = "v3", **kwargs
    ) -> AsyncGenerator[Any, None]:
        url = self._get_full_url(endpoint, version)
        request_args = self._prepare_request_args(endpoint, **kwargs)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(method, url, **request_args) as response:
                await self._handle_response(response)
                async for line in response.aiter_lines():
                    if line.strip():  # Ignore empty lines
                        try:
                            yield json.loads(line)
                        except Exception:
                            yield line

    async def _handle_response(self, response):
        if response.status_code >= 400:
            try:
                error_content = response.json()
                if isinstance(error_content, dict):
                    message = (
                        error_content.get("detail", {}).get(
                            "message", str(error_content)
                        )
                        if isinstance(error_content.get("detail"), dict)
                        else error_content.get("detail", str(error_content))
                    )
                else:
                    message = str(error_content)
            except json.JSONDecodeError:
                message = response.text
            except Exception as e:
                message = str(e)

            raise R2RException(
                status_code=response.status_code, message=message
            )

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def set_api_key(self, api_key: str) -> None:
        if self.access_token:
            raise ValueError("Cannot have both access token and api key.")
        self.api_key = api_key

    def unset_api_key(self) -> None:
        self.api_key = None

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url
