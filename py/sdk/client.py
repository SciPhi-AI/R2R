# client.py

import httpx
from .base_client import BaseClient, handle_request_error
from .auth import AuthMixin
# Import other mixins as needed
from .models import R2RException, Token, UserResponse
from typing import Any, Dict, Optional

class R2RClient(BaseClient, AuthMixin):
    def __init__(
        self,
        base_url: str = "http://localhost:7272",
        prefix: str = "/v2",
        timeout: float = 300.0,
    ):
        super().__init__(base_url, prefix, timeout)
        self.client = httpx.Client(timeout=self.timeout)

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = self._build_url(endpoint)
        headers = kwargs.pop("headers", {})
        headers.update(self._get_auth_header())
        try:
            response = self.client.request(
                method, url, headers=headers, **kwargs
            )
            handle_request_error(response)
            return response.json() if response.content else None
        except httpx.RequestError as e:
            raise R2RException(
                status_code=500, message=f"Request failed: {str(e)}"
            ) from e

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        return self._make_request(method, endpoint, **kwargs)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
