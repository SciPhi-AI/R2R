from __future__ import annotations  # for Python 3.10+

from typing import Optional

from typing_extensions import deprecated


class SyncServerMixins:
    def health(self) -> dict:
        return self._make_request("GET", "health")  # type: ignore

    def server_stats(self) -> dict:
        """
        Get statistics about the server, including the start time, uptime, CPU usage, and memory usage.

        Returns:
            dict: The server statistics.
        """
        return self._make_request("GET", "server_stats")  # type: ignore

    @deprecated("Use client.system.logs() instead")
    def logs(
        self,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        run_type_filter: Optional[str] = None,
    ) -> dict:
        """
        Get logs from the server.

        Args:
            offset (Optional[int]): The offset to start from.
            limit (Optional[int]): The maximum number of logs to return.
            run_type_filter (Optional[str]): The run type to filter by.

        Returns:
            dict: The logs from the server.
        """
        params = {
            key: value
            for key, value in {
                "offset": offset,
                "limit": limit,
                "run_type_filter": run_type_filter,
            }.items()
            if value is not None
        }
        return self._make_request("GET", "logs", params=params)  # type: ignore
