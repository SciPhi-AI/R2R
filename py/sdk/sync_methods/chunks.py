import json
from typing import Any, Optional
from uuid import UUID

from shared.api.models import (
    WrappedBooleanResponse,
    WrappedChunkResponse,
    WrappedChunksResponse,
    WrappedVectorSearchResponse,
)

from ..models import SearchSettings


class ChunksSDK:
    """SDK for interacting with chunks in the v3 API."""

    def __init__(self, client):
        self.client = client

    def update(
        self,
        chunk: dict[str, str],
    ) -> WrappedChunkResponse:
        """Update an existing chunk.

        Args:
            chunk (dict[str, str]): Chunk to update. Should contain:
                - id: UUID of the chunk
                - metadata: Dictionary of metadata
        Returns:
            WrappedChunkResponse
        """
        response_dict = self.client._make_request(
            "POST",
            f"chunks/{str(chunk['id'])}",
            json=chunk,
            version="v3",
        )

        return WrappedChunkResponse(**response_dict)

    def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedChunkResponse:
        """Get a specific chunk.

        Args:
            id (str | UUID): Chunk ID to retrieve

        Returns:
            WrappedChunkResponse
        """

        response_dict = self.client._make_request(
            "GET",
            f"chunks/{id}",
            version="v3",
        )

        return WrappedChunkResponse(**response_dict)

    # FIXME: Is this the most appropriate name for this method?
    def list_by_document(
        self,
        document_id: str | UUID,
        metadata_filter: Optional[dict] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedChunksResponse:
        """List chunks for a specific document.

        Args:
            document_id (str | UUID): Document ID to get chunks for
            metadata_filter (Optional[dict]): Filter chunks by metadata
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedChunksResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if metadata_filter:
            params["metadata_filter"] = json.dumps(metadata_filter)

        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(document_id)}/chunks",
            params=params,
            version="v3",
        )

        return WrappedChunksResponse(**response_dict)

    def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Delete a specific chunk.

        Args:
            id (str | UUID): ID of chunk to delete

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE",
            f"chunks/{str(id)}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def list(
        self,
        include_vectors: bool = False,
        metadata_filter: Optional[dict] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        filters: Optional[dict] = None,
    ) -> WrappedChunksResponse:
        """List chunks with pagination support.

        Args:
            include_vectors (bool, optional): Include vector data in response. Defaults to False.
            metadata_filter (Optional[dict], optional): Filter by metadata. Defaults to None.
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedChunksResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
            "include_vectors": include_vectors,
        }
        if filters:
            params["filters"] = json.dumps(filters)

        if metadata_filter:
            params["metadata_filter"] = json.dumps(metadata_filter)

        response_dict = self.client._make_request(
            "GET",
            "chunks",
            params=params,
            version="v3",
        )

        return WrappedChunksResponse(**response_dict)

    def search(
        self,
        query: str,
        search_settings: Optional[dict | SearchSettings] = None,
    ) -> WrappedVectorSearchResponse:
        """Conduct a vector and/or graph search.

        Args:
            query (str): The query to search for.
            search_settings (Optional[dict, SearchSettings]]): Vector search settings.

        Returns:
            WrappedVectorSearchResponse
        """
        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()

        data: dict[str, Any] = {
            "query": query,
            "search_settings": search_settings,
        }
        response_dict = self.client._make_request(
            "POST",
            "chunks/search",
            json=data,
            version="v3",
        )

        return WrappedVectorSearchResponse(**response_dict)
