from typing import Optional


class ServerMethods:
    @staticmethod
    async def health(self) -> dict:
        return await self._make_request("GET", "health")

    @staticmethod
    async def server_stats(client) -> dict:
        """
        Get statistics about the server, including the start time, uptime, CPU usage, and memory usage.

        Returns:
            dict: The server statistics.
        """
        return await client._make_request("GET", "server_stats")

    @staticmethod
    async def logs(
        client,
        run_type_filter: Optional[str] = None,
        max_runs: int = None,
    ) -> dict:
        """
        Get logs from the server.

        Args:
            run_type_filter (Optional[str]): The run type to filter by.
            max_runs (int): Specifies the maximum number of runs to return. Values outside the range of 1 to 1000 will be adjusted to the nearest valid value with a default of 100.

        Returns:
            dict: The logs from the server.
        """
        params = {}
        if run_type_filter is not None:
            params["run_type_filter"] = run_type_filter
        if max_runs is not None:
            params["max_runs"] = max_runs
        return await client._make_request("GET", "logs", params=params)
