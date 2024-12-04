import json
from typing import Optional

from shared.api.models.base import WrappedGenericMessageResponse
from shared.api.models.ingestion.responses import (
    WrappedListVectorIndicesResponse,
)


class IndicesSDK:
    def __init__(self, client):
        self.client = client

    async def create(
        self,
        config: dict,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedGenericMessageResponse:
        """
        Create a new vector similarity search index in the database.

        Args:
            config (Union[dict, IndexConfig]): Configuration for the vector index.
            run_with_orchestration (Optional[bool]): Whether to run index creation as an orchestrated task.
        """
        if not isinstance(config, dict):
            config = config.model_dump()

        data = {
            "config": config,
            "run_with_orchestration": run_with_orchestration,
        }
        return await self.client._make_request(
            "POST",
            "indices",
            json=data,
            version="v3",
        )

    async def list(
        self,
        filters: Optional[dict] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 10,
    ) -> WrappedListVectorIndicesResponse:
        """
        List existing vector similarity search indices with pagination support.

        Args:
            filters (Optional[dict]): Filter criteria for indices.
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedListVectorIndicesResponse: The response containing the list of indices.
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if filters:
            params["filters"] = json.dumps(filters)
        return await self.client._make_request(
            "GET",
            "indices",
            params=params,
            version="v3",
        )

    async def retrieve(
        self,
        index_name: str,
        table_name: str = "vectors",
    ) -> dict:
        """
        Get detailed information about a specific vector index.

        Args:
            index_name (str): The name of the index to retrieve.
            table_name (str): The name of the table where the index is stored.

        Returns:
            WrappedGetIndexResponse: The response containing the index details.
        """
        return await self.client._make_request(
            "GET",
            f"indices/{table_name}/{index_name}",
            version="v3",
        )

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

    async def delete(
        self,
        index_name: str,
        table_name: str = "vectors",
    ) -> WrappedGenericMessageResponse:
        """
        Delete an existing vector index.

        Args:
            index_name (str): The name of the index to retrieve.
            table_name (str): The name of the table where the index is stored.

        Returns:
            WrappedGetIndexResponse: The response containing the index details.
        """
        return await self.client._make_request(
            "DELETE",
            f"indices/{table_name}/{index_name}",
            version="v3",
        )
