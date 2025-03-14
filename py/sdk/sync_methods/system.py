from shared.api.models import (
    WrappedGenericMessageResponse,
    WrappedServerStatsResponse,
    WrappedSettingsResponse,
)


class SystemSDK:
    def __init__(self, client):
        self.client = client

    def health(self) -> WrappedGenericMessageResponse:
        """Check the health of the R2R server."""
        response_dict = self.client._make_request(
            "GET", "health", version="v3"
        )

        return WrappedGenericMessageResponse(**response_dict)

    def settings(self) -> WrappedSettingsResponse:
        """Get the configuration settings for the R2R server.

        Returns:
            dict: The server settings.
        """
        response_dict = self.client._make_request(
            "GET", "system/settings", version="v3"
        )

        return WrappedSettingsResponse(**response_dict)

    def status(self) -> WrappedServerStatsResponse:
        """Get statistics about the server, including the start time, uptime,
        CPU usage, and memory usage.

        Returns:
            dict: The server statistics.
        """
        response_dict = self.client._make_request(
            "GET", "system/status", version="v3"
        )

        return WrappedServerStatsResponse(**response_dict)
