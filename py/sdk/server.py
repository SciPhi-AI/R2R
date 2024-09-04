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
        offset: int = None,
        limit: int = None,
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
        return await client._make_request("GET", "logs", params=params)
