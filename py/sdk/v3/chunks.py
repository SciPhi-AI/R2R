import json
from inspect import getmembers, isasyncgenfunction, iscoroutinefunction
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from shared.abstractions import VectorSearchSettings

from ..base.base_client import sync_generator_wrapper, sync_wrapper
from ..models import CombinedSearchResponse


class ChunksSDK:
    """
    SDK for interacting with chunks in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        chunks: List[Dict[str, Any]],
        run_with_orchestration: Optional[bool] = None,
    ) -> dict:
        """
        Create multiple chunks.

        Args:
            chunks (List[Dict[str, Any]]): List of chunks to create. Each chunk should contain:
                - document_id: UUID of the document
                - collection_ids: List of collection UUIDs
                - metadata: Dictionary of metadata

        Returns:
            dict: Creation results containing processed chunk information
        """
        data: dict = {}
        data["raw_chunks"] = chunks  # json.dumps(chunks)
        if run_with_orchestration != None:
            data["run_with_orchestration"] = run_with_orchestration
        return await self.client._make_request("POST", "chunks", json=data)

    async def update(
        self,
        chunk: dict[str, str],
    ) -> dict:
        """
        Update an existing chunk.

        Args:
            chunk (dict[str, str]): Chunk to update. Should contain:
                - id: UUID of the chunk
                - metadata: Dictionary of metadata
        Returns:
            dict: Update results containing processed chunk information
        """
        return await self.client._make_request(
            "POST",
            f"chunks/{str(chunk['id'])}",
            json=chunk,
        )

    async def retrieve(
        self,
        id: Union[str, UUID],
    ) -> dict:
        """
        Get a specific chunk.

        Args:
            id (Union[str, UUID]): Chunk ID to retrieve

        Returns:
            dict: List of chunks and pagination information
        """

        return await self.client._make_request(
            "GET",
            f"chunks/{id}",
        )

    async def list_by_document(
        self,
        document_id: Union[str, UUID],
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """
        List chunks for a specific document.

        Args:
            document_id (Union[str, UUID]): Document ID to get chunks for
            offset (Optional[int]): Pagination offset
            limit (Optional[int]): Maximum number of chunks to return
            metadata_filter (Optional[Dict[str, Any]]): Filter chunks by metadata

        Returns:
            dict: List of chunks and pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if metadata_filter:
            params["metadata_filter"] = json.dumps(metadata_filter)

        return await self.client._make_request(
            "GET", f"documents/{str(document_id)}/chunks", params=params
        )

    async def delete(
        self,
        id: Union[str, UUID],
    ) -> None:
        """
        Delete a specific chunk.

        Args:
            id (Union[str, UUID]): ID of chunk to delete
        """
        await self.client._make_request("DELETE", f"chunks/{str(id)}")

    async def list(
        self,
        offset: int = 0,
        limit: int = 10,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
        metadata_filter: Optional[Dict[str, Any]] = None,
        include_vectors: bool = False,
    ) -> dict:
        """
        List chunks with pagination support.

        Args:
            offset (int, optional): Number of records to skip. Defaults to 0.
            limit (int, optional): Maximum number of records to return. Defaults to 10.
            sort_by (str, optional): Field to sort by. Defaults to 'created_at'.
            sort_order (str, optional): Sort order ('ASC' or 'DESC'). Defaults to 'DESC'.
            metadata_filter (Optional[Dict[str, Any]], optional): Filter by metadata. Defaults to None.
            include_vectors (bool, optional): Include vector data in response. Defaults to False.

        Returns:
            dict: Dictionary containing:
                - results: List of chunks
                - page_info: Pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "include_vectors": include_vectors,
        }

        if metadata_filter:
            params["metadata_filter"] = json.dumps(metadata_filter)

        return await self.client._make_request("GET", "chunks", params=params)

    async def search(
        self,
        query: str,
        vector_search_settings: Optional[
            Union[dict, VectorSearchSettings]
        ] = None,
    ) -> CombinedSearchResponse:
        """
        Conduct a vector and/or KG search.

        Args:
            query (str): The query to search for.
            vector_search_settings (Optional[Union[dict, VectorSearchSettings]]): Vector search settings.
            kg_search_settings (Optional[Union[dict, KGSearchSettings]]): KG search settings.

        Returns:
            CombinedSearchResponse: The search response.
        """
        if vector_search_settings and not isinstance(
            vector_search_settings, dict
        ):
            vector_search_settings = vector_search_settings.model_dump()

        data = {
            "query": query,
            "vector_search_settings": vector_search_settings or {},
        }
        return await self.client._make_request("POST", "chunks/search", json=data)  # type: ignore


class SyncChunkSDK:
    """Synchronous wrapper for ChunksSDK"""

    def __init__(self, async_sdk: ChunksSDK):
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
