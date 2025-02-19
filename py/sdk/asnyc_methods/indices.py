import json
from typing import Any, Optional

from shared.api.models import (
    WrappedGenericMessageResponse,
    WrappedVectorIndexResponse,
    WrappedVectorIndicesResponse,
)


class IndicesSDK:
    def __init__(self, client):
        self.client = client

    async def create(
        self,
        config: dict,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedGenericMessageResponse:
        """Create a new vector similarity search index in the database.

        Args:
            config (dict | IndexConfig): Configuration for the vector index.
            run_with_orchestration (Optional[bool]): Whether to run index creation as an orchestrated task.
        """
        if not isinstance(config, dict):
            config = config.model_dump()

        data: dict[str, Any] = {
            "config": config,
            "run_with_orchestration": run_with_orchestration,
        }
        response_dict = await self.client._make_request(
            "POST",
            "indices",
            json=data,
            version="v3",
        )

        return WrappedGenericMessageResponse(**response_dict)

    async def list(
        self,
        filters: Optional[dict] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 10,
    ) -> WrappedVectorIndicesResponse:
        """List existing vector similarity search indices with pagination
        support.

        Args:
            filters (Optional[dict]): Filter criteria for indices.
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedVectorIndicesResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if filters:
            params["filters"] = json.dumps(filters)
        response_dict = await self.client._make_request(
            "GET",
            "indices",
            params=params,
            version="v3",
        )

        return WrappedVectorIndicesResponse(**response_dict)

    async def retrieve(
        self,
        index_name: str,
        table_name: str = "vectors",
    ) -> WrappedVectorIndexResponse:
        """Get detailed information about a specific vector index.

        Args:
            index_name (str): The name of the index to retrieve.
            table_name (str): The name of the table where the index is stored.

        Returns:
            WrappedGetIndexResponse: The response containing the index details.
        """
        response_dict = await self.client._make_request(
            "GET",
            f"indices/{table_name}/{index_name}",
            version="v3",
        )

        return WrappedVectorIndexResponse(**response_dict)

    async def delete(
        self,
        index_name: str,
        table_name: str = "vectors",
    ) -> WrappedGenericMessageResponse:
        """Delete an existing vector index.

        Args:
            index_name (str): The name of the index to retrieve.
            table_name (str): The name of the table where the index is stored.

        Returns:
            WrappedGetIndexResponse: The response containing the index details.
        """
        response_dict = await self.client._make_request(
            "DELETE",
            f"indices/{table_name}/{index_name}",
            version="v3",
        )

        return WrappedGenericMessageResponse(**response_dict)
