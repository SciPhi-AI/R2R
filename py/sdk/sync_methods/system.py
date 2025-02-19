from typing import Optional

from shared.api.models import (
    WrappedGenericMessageResponse,
    WrappedLogsResponse,
    WrappedServerStatsResponse,
    WrappedSettingsResponse,
)


class SystemSDK:

    def __init__(self, client):
        self.client = client

    def health(self) -> WrappedGenericMessageResponse:
        """Check the health of the R2R server."""
        response_dict = self.client._make_request("GET",
                                                  "health",
                                                  version="v3")

        return WrappedGenericMessageResponse(**response_dict)

    def logs(
        self,
        run_type_filter: Optional[str] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedLogsResponse:
        """Get logs from the server.

        Args:
            run_type_filter (Optional[str]): The run type to filter by.
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: The logs from the server.
        """
        params = {
            key: value
            for key, value in {
                "run_type_filter": run_type_filter,
                "offset": offset,
                "limit": limit,
            }.items() if value is not None
        }
        response_dict = self.client._make_request("GET",
                                                  "system/logs",
                                                  params=params,
                                                  version="v3")

        return WrappedLogsResponse(**response_dict)

    def settings(self) -> WrappedSettingsResponse:
        """Get the configuration settings for the R2R server.

        Returns:
            dict: The server settings.
        """
        response_dict = self.client._make_request("GET",
                                                  "system/settings",
                                                  version="v3")

        return WrappedSettingsResponse(**response_dict)

    def status(self) -> WrappedServerStatsResponse:
        """Get statistics about the server, including the start time, uptime,
        CPU usage, and memory usage.

        Returns:
            dict: The server statistics.
        """
        response_dict = self.client._make_request("GET",
                                                  "system/status",
                                                  version="v3")

        return WrappedServerStatsResponse(**response_dict)
