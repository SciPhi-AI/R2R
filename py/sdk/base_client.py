# base_client.py

import json
from typing import Any, Dict, Optional

import httpx

from .models import R2RException

# Common error handling functions
def handle_request_error(response):
    if response.status_code < 400:
        return
    try:
        error_content = response.json()
        message = error_content.get("detail", str(response.text))
    except json.JSONDecodeError:
        message = response.text
    raise R2RException(status_code=response.status_code, message=message)

async def handle_request_error_async(response):
    if response.status_code < 400:
        return
    try:
        if response.headers.get("content-type") == "application/json":
            error_content = await response.json()
        else:
            error_content = await response.text()
        message = error_content.get("detail", str(error_content))
    except Exception:
        message = response.text
    raise R2RException(status_code=response.status_code, message=message)

class BaseClient:
    def __init__(
        self,
        base_url: str = "http://localhost:7272",
        prefix: str = "/v2",
        timeout: float = 300.0,
    ):
        self.base_url = base_url
        self.prefix = prefix
        self.access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self.timeout = timeout

    def _get_auth_header(self) -> Dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def _build_url(self, endpoint: str) -> str:
        return f"{self.base_url}{self.prefix}/{endpoint}"
