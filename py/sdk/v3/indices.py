import json
import logging
from inspect import isasyncgenfunction, iscoroutinefunction
from typing import Optional

from ..base.base_client import sync_generator_wrapper, sync_wrapper

logger = logging.getLogger()


class IndicesSDK:
    def __init__(self, client):
        self.client = client

    async def create_index(
        self,
        config: dict,  # Union[dict, IndexConfig],
        run_with_orchestration: Optional[bool] = True,
    ) -> dict:
        """
        Create a new vector similarity search index in the database.

        Args:
            config (Union[dict, IndexConfig]): Configuration for the vector index.
            run_with_orchestration (Optional[bool]): Whether to run index creation as an orchestrated task.

        Returns:
            WrappedCreateVectorIndexResponse: The response containing the created index details.
        """
        if not isinstance(config, dict):
            config = config.model_dump()

        data = {
            "config": config,
            "run_with_orchestration": run_with_orchestration,
        }
        return await self.client._make_request("POST", "indices", json=data)  # type: ignore

    async def list_indices(
        self,
        offset: int = 0,
        limit: int = 10,
        filters: Optional[dict] = None,
    ) -> dict:
        """
        List existing vector similarity search indices with pagination support.

        Args:
            offset (int): Number of records to skip.
            limit (int): Maximum number of records to return.
            filters (Optional[dict]): Filter criteria for indices.

        Returns:
            WrappedListVectorIndicesResponse: The response containing the list of indices.
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if filters:
            params["filters"] = json.dumps(filters)
        return await self.client._make_request("GET", "indices", params=params)  # type: ignore

    async def get_index(
        self,
        index_name: str,
        table_name: str = "vectors",
    ) -> dict:
        """
        Get detailed information about a specific vector index.

        Args:
            id (Union[str, UUID]): The ID of the index to retrieve.

        Returns:
            WrappedGetIndexResponse: The response containing the index details.
        """
        return await self.client._make_request("GET", f"indices/{table_name}/{index_name}")  # type: ignore

    # async def update_index(
    #     self,
    #     id: Union[str, UUID],
    #     config: dict,  # Union[dict, IndexConfig],
    #     run_with_orchestration: Optional[bool] = True,
    # ) -> dict:
    #     """
    #     Update an existing index's configuration.

    #     Args:
    #         id (Union[str, UUID]): The ID of the index to update.
    #         config (Union[dict, IndexConfig]): The new configuration for the index.
    #         run_with_orchestration (Optional[bool]): Whether to run the update as an orchestrated task.

    #     Returns:
    #         WrappedUpdateIndexResponse: The response containing the updated index details.
    #     """
    #     if not isinstance(config, dict):
    #         config = config.model_dump()

    #     data = {
    #         "config": config,
    #         "run_with_orchestration": run_with_orchestration,
    #     }
    #     return await self.client._make_request("POST", f"indices/{id}", json=data)  # type: ignore

    async def delete_index(
        self,
        index_name: str,
        table_name: str = "vectors",
    ) -> dict:
        """
        Get detailed information about a specific vector index.

        Args:
            id (Union[str, UUID]): The ID of the index to retrieve.

        Returns:
            WrappedGetIndexResponse: The response containing the index details.
        """
        return await self.client._make_request("DELETE", f"indices/{table_name}/{index_name}")  # type: ignore


class SyncIndexSDK:
    """Synchronous wrapper for DocumentsSDK"""

    def __init__(self, async_sdk: IndicesSDK):
        self._async_sdk = async_sdk

        # Get all attributes from the instance
        for name in dir(async_sdk):
            if not name.startswith("_"):  # Skip private methods
                attr = getattr(async_sdk, name)
                # Check if it's a method and if it's async
                if callable(attr) and (
                    iscoroutinefunction(attr) or isasyncgenfunction(attr)
                ):
                    if isasyncgenfunction(attr):
                        setattr(self, name, sync_generator_wrapper(attr))
                    else:
                        setattr(self, name, sync_wrapper(attr))
