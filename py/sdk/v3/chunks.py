import json
from typing import Optional
from uuid import UUID

from shared.api.models.base import WrappedBooleanResponse
from shared.api.models.management.responses import (
    WrappedChunkResponse,
    WrappedChunksResponse,
)

from ..models import SearchSettings


class ChunksSDK:
    """
    SDK for interacting with chunks in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        chunks: list[dict],
        run_with_orchestration: Optional[bool] = True,
    ) -> list[dict]:
        """
        Create multiple chunks.

        Args:
            chunks: List of UnprocessedChunk objects containing:
                - id: Optional[UUID]
                - document_id: Optional[UUID]
                - collection_ids: list[UUID]
                - metadata: dict
                - text: str
            run_with_orchestration: Whether to run the chunks through orchestration

        Returns:
            list[dict]: List of creation results containing processed chunk information
        """
        data = {
            "chunks": chunks,
            "run_with_orchestration": run_with_orchestration,
        }
        return await self.client._make_request(
            "POST",
            "chunks",
            json=data,
            version="v3",
        )

    async def update(
        self,
        chunk: dict[str, str],
    ) -> WrappedChunkResponse:
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
            version="v3",
        )

    async def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedChunkResponse:
        """
        Get a specific chunk.

        Args:
            id (str | UUID): Chunk ID to retrieve

        Returns:
            dict: List of chunks and pagination information
        """

        return await self.client._make_request(
            "GET",
            f"chunks/{id}",
            version="v3",
        )

    # FIXME: Is this the most appropriate name for this method?
    async def list_by_document(
        self,
        document_id: str | UUID,
        metadata_filter: Optional[dict] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedChunksResponse:
        """
        List chunks for a specific document.

        Args:
            document_id (str | UUID): Document ID to get chunks for
            metadata_filter (Optional[dict]): Filter chunks by metadata
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

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
            "GET",
            f"documents/{str(document_id)}/chunks",
            params=params,
            version="v3",
        )

    async def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Delete a specific chunk.

        Args:
            id (Union[str, UUID]): ID of chunk to delete
        """
        return await self.client._make_request(
            "DELETE",
            f"chunks/{str(id)}",
            version="v3",
        )

    async def list(
        self,
        include_vectors: bool = False,
        metadata_filter: Optional[dict] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedChunksResponse:
        """
        List chunks with pagination support.

        Args:
            include_vectors (bool, optional): Include vector data in response. Defaults to False.
            metadata_filter (Optional[dict], optional): Filter by metadata. Defaults to None.
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: Dictionary containing:
                - results: List of chunks
                - page_info: Pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
            "include_vectors": include_vectors,
        }

        if metadata_filter:
            params["metadata_filter"] = json.dumps(metadata_filter)

        return await self.client._make_request(
            "GET",
            "chunks",
            params=params,
            version="v3",
        )

    async def search(
        self,
        query: str,
        search_settings: Optional[dict | SearchSettings] = None,
    ):  # -> CombinedSearchResponse:
        """
        Conduct a vector and/or KG search.

        Args:
            query (str): The query to search for.
            search_settings (Optional[dict, SearchSettings]]): Vector search settings.

        Returns:
            CombinedSearchResponse: The search response.
        """
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data = {
            "query": query,
            "search_settings": search_settings,
        }
        return await self.client._make_request(
            "POST",
            "chunks/search",
            json=data,
            version="v3",
        )
