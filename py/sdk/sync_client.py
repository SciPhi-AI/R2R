import json
from io import BytesIO
from typing import Any, Generator

from httpx import Client, RequestError, Response

from shared.abstractions import R2RException

from .base.base_client import BaseClient
from .sync_methods import (
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


class R2RClient(BaseClient):
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 300.0,
        custom_client=None,
    ):
        super().__init__(base_url, timeout)
        self.client = custom_client or Client(timeout=timeout)
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

    def _make_request(
        self, method: str, endpoint: str, version: str = "v3", **kwargs
    ) -> dict[str, Any] | BytesIO | None:
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
            response = self.client.request(method, url, **request_args)
            self._handle_response(response)

            if "application/json" in response.headers.get("Content-Type", ""):
                return response.json() if response.content else None
            else:
                return BytesIO(response.content)

        except RequestError as e:
            raise R2RException(
                status_code=500,
                message=f"Request failed: {str(e)}",
            ) from e

    def _make_streaming_request(
        self, method: str, endpoint: str, version: str = "v3", **kwargs
    ) -> Generator[dict[str, str], None, None]:
        """
        Make a streaming request, parsing Server-Sent Events (SSE) in multiline form.

        Yields a dictionary with keys:
        - "event": the event type (or "unknown" if not provided)
        - "data": the JSON string (possibly spanning multiple lines) accumulated from the event's data lines
        """
        url = self._get_full_url(endpoint, version)
        request_args = self._prepare_request_args(endpoint, **kwargs)

        with Client(timeout=self.timeout) as client:
            with client.stream(method, url, **request_args) as response:
                self._handle_response(response)

                sse_event_block: dict[str, Any] = {"event": None, "data": []}

                for line in response.iter_lines():
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", "replace")

                    # Blank line -> end of this SSE event
                    if line == "":
                        # If there's any accumulated data, yield this event
                        if sse_event_block["data"]:
                            data_str = "".join(sse_event_block["data"])
                            yield {
                                "event": sse_event_block["event"] or "unknown",
                                "data": data_str,
                            }
                        # Reset the block
                        sse_event_block = {"event": None, "data": []}
                        continue

                    # Otherwise, parse the line
                    if line.startswith("event:"):
                        sse_event_block["event"] = line[
                            len("event:") :
                        ].lstrip()
                    elif line.startswith("data:"):
                        # Accumulate the exact substring after "data:"
                        # Notice we do *not* strip() the entire line
                        chunk = line[len("data:") :]
                        sse_event_block["data"].append(chunk)
                    # Optionally handle id:, retry:, etc. if needed

                # If something remains in the buffer at the end
                if sse_event_block["data"]:
                    data_str = "".join(sse_event_block["data"])
                    yield {
                        "event": sse_event_block["event"] or "unknown",
                        "data": data_str,
                    }

    def _handle_response(self, response: Response) -> None:
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

    def set_api_key(self, api_key: str) -> None:
        if self.access_token:
            raise ValueError("Cannot have both access token and api key.")
        self.api_key = api_key

    def unset_api_key(self) -> None:
        self.api_key = None

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url
