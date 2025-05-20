import os

from shared.abstractions import R2RClientException


class BaseClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 300.0,
    ):
        self.base_url = base_url or os.getenv(
            "R2R_API_BASE", "http://localhost:7272"
        )
        self.timeout = timeout
        self.access_token: str | None = None
        self._refresh_token: str | None = None
        self._user_id: str | None = None
        self.api_key: str | None = os.getenv("R2R_API_KEY", None)
        self.project_name: str | None = None

    def _get_auth_header(self) -> dict[str, str]:
        if self.access_token and self.api_key:
            raise R2RClientException(
                message="Cannot have both access token and api key.",
            )
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        elif self.api_key:
            return {"x-api-key": self.api_key}
        else:
            return {}

    def _get_full_url(self, endpoint: str, version: str = "v3") -> str:
        return f"{self.base_url}/{version}/{endpoint}"

    def _prepare_request_args(self, endpoint: str, **kwargs) -> dict:
        headers = kwargs.pop("headers", {})
        if (self.access_token or self.api_key) and endpoint not in [
            "register",
            "login",
            "verify_email",
        ]:
            headers.update(self._get_auth_header())

        if self.project_name:
            headers["x-project-name"] = self.project_name

        if (
            kwargs.get("params", None) == {}
            or kwargs.get("params", None) is None
        ):
            kwargs.pop("params", None)

        return {"headers": headers, **kwargs}
