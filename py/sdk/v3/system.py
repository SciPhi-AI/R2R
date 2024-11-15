from typing import Optional


class SystemSDK:
    def __init__(self, client):
        self.client = client

    async def health(self) -> dict:
        return await self.client._make_request("GET", "health", version="v3")

    async def status(self) -> dict:
        """
        Get statistics about the server, including the start time, uptime, CPU usage, and memory usage.

        Returns:
            dict: The server statistics.
        """
        return await self.client._make_request(
            "GET", "system/status", version="v3"
        )

    async def logs(
        self,
        run_type_filter: Optional[str] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> dict:
        """
        Get logs from the server.

        Args:
            run_type_filter (Optional[str]): The run type to filter by.
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100..

        Returns:
            dict: The logs from the server.
        """
        params = {
            key: value
            for key, value in {
                "run_type_filter": run_type_filter,
                "offset": offset,
                "limit": limit,
            }.items()
            if value is not None
        }
        return await self.client._make_request(
            "GET", "system/logs", params=params, version="v3"
        )
