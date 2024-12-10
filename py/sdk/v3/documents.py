import json
from io import BytesIO
from typing import Optional
from uuid import UUID

from shared.api.models.base import WrappedBooleanResponse
from shared.api.models.ingestion.responses import WrappedIngestionResponse
from shared.api.models.management.responses import (
    WrappedChunksResponse,
    WrappedCollectionsResponse,
    WrappedDocumentResponse,
    WrappedDocumentsResponse,
)

from ..models import IngestionMode, SearchMode, SearchSettings


class DocumentsSDK:
    """
    SDK for interacting with documents in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        file_path: Optional[str] = None,
        raw_text: Optional[str] = None,
        chunks: Optional[list[str]] = None,
        id: Optional[str | UUID] = None,
        ingestion_mode: Optional[str] = None,
        collection_ids: Optional[list[str | UUID]] = None,
        metadata: Optional[dict] = None,
        ingestion_config: Optional[dict | IngestionMode] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedIngestionResponse:
        """
        Create a new document from either a file or content.

        Args:
            file_path (Optional[str]): The file to upload, if any
            content (Optional[str]): Optional text content to upload, if no file path is provided
            id (Optional[Union[str, UUID]]): Optional ID to assign to the document
            collection_ids (Optional[list[Union[str, UUID]]]): Collection IDs to associate with the document. If none are provided, the document will be assigned to the user's default collection.
            metadata (Optional[dict]): Optional metadata to assign to the document
            ingestion_config (Optional[dict]): Optional ingestion configuration to use
            run_with_orchestration (Optional[bool]): Whether to run with orchestration
        """
        if not file_path and not raw_text and not chunks:
            raise ValueError(
                "Either `file_path`, `raw_text` or `chunks` must be provided"
            )
        if (
            (file_path and raw_text)
            or (file_path and chunks)
            or (raw_text and chunks)
        ):
            raise ValueError(
                "Only one of `file_path`, `raw_text` or `chunks` may be provided"
            )

        data = {}
        files = None

        if id:
            data["id"] = str(id)  # json.dumps(str(id))
        if metadata:
            data["metadata"] = json.dumps(metadata)
        if ingestion_config:
            if not isinstance(ingestion_config, dict):
                ingestion_config = ingestion_config.model_dump()
            ingestion_config["app"] = {}
            data["ingestion_config"] = json.dumps(ingestion_config)
        if collection_ids:
            collection_ids = [str(collection_id) for collection_id in collection_ids]  # type: ignore
            data["collection_ids"] = json.dumps(collection_ids)
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = str(run_with_orchestration)
        if ingestion_mode is not None:
            data["ingestion_mode"] = ingestion_mode
        if file_path:
            # Create a new file instance that will remain open during the request
            file_instance = open(file_path, "rb")
            files = [
                (
                    "file",
                    (file_path, file_instance, "application/octet-stream"),
                )
            ]
            try:
                result = await self.client._make_request(
                    "POST",
                    "documents",
                    data=data,
                    files=files,
                    version="v3",
                )
            finally:
                # Ensure we close the file after the request is complete
                file_instance.close()
            return result
        elif raw_text:
            data["raw_text"] = raw_text  # type: ignore
            return await self.client._make_request(
                "POST",
                "documents",
                data=data,
                version="v3",
            )
        else:
            data["chunks"] = json.dumps(chunks)
            return await self.client._make_request(
                "POST",
                "documents",
                data=data,
                version="v3",
            )

    async def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedDocumentResponse:
        """
        Get a specific document by ID.

        Args:
            id (Union[str, UUID]): ID of document to retrieve

        Returns:
            dict: Document information
        """
        return await self.client._make_request(
            "GET",
            f"documents/{str(id)}",
            version="v3",
        )

    # you could do something like:
    async def download(
        self,
        id: str | UUID,
    ) -> BytesIO:
        response = await self.client._make_request(
            "GET",
            f"documents/{str(id)}/download",
            version="v3",
            # No json parsing here, if possible
        )
        print(response)
        if not isinstance(response, BytesIO):
            raise ValueError("Expected BytesIO response")
        return response

    async def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Delete a specific document.

        Args:
            id (Union[str, UUID]): ID of document to delete
        """
        return await self.client._make_request(
            "DELETE",
            f"documents/{str(id)}",
            version="v3",
        )

    async def list_chunks(
        self,
        id: str | UUID,
        include_vectors: Optional[bool] = False,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedChunksResponse:
        """
        Get chunks for a specific document.

        Args:
            id (Union[str, UUID]): ID of document to retrieve chunks for
            include_vectors (Optional[bool]): Whether to include vector embeddings in the response
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of document chunks and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
            "include_vectors": include_vectors,
        }
        return await self.client._make_request(
            "GET",
            f"documents/{str(id)}/chunks",
            params=params,
            version="v3",
        )

    async def list_collections(
        self,
        id: str | UUID,
        include_vectors: Optional[bool] = False,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedCollectionsResponse:
        """
        List collections for a specific document.

        Args:
            id (Union[str, UUID]): ID of document to retrieve collections for
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of document chunks and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
        }

        return await self.client._make_request(
            "GET",
            f"documents/{str(id)}/collections",
            params=params,
            version="v3",
        )

    async def delete_by_filter(
        self,
        filters: dict,
    ) -> WrappedBooleanResponse:
        """
        Delete documents based on filters.

        Args:
            filters (dict): Filters to apply when selecting documents to delete
        """
        filters_json = json.dumps(filters)
        return await self.client._make_request(
            "DELETE",
            "documents/by-filter",
            data=filters_json,
            # params={"filters": filters_json},
            # data=filters,
            version="v3",
        )

    async def extract(
        self,
        id: str | UUID,
        run_type: Optional[str] = None,
        settings: Optional[dict] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> dict:
        """
        Extract entities and relationships from a document.

        Args:
            id (Union[str, UUID]): ID of document to extract from
            run_type (Optional[str]): Whether to return an estimate or run extraction
            settings (Optional[dict]): Settings for extraction process
            run_with_orchestration (Optional[bool]): Whether to run with orchestration

        Returns:
            dict: Extraction results or cost estimate
        """
        data = {}
        if run_type:
            data["run_type"] = run_type
        if settings:
            data["settings"] = json.dumps(settings)
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = str(run_with_orchestration)

        return await self.client._make_request(
            "POST",
            f"documents/{str(id)}/extract",
            params=data,
            version="v3",
        )

    async def list_entities(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        include_embeddings: Optional[bool] = False,
    ) -> dict:
        """
        List entities extracted from a document.

        Args:
            id (Union[str, UUID]): ID of document to get entities from
            offset (Optional[int]): Number of items to skip
            limit (Optional[int]): Max number of items to return
            include_embeddings (Optional[bool]): Whether to include embeddings

        Returns:
            dict: List of entities and pagination info
        """
        params = {
            "offset": offset,
            "limit": limit,
            "include_embeddings": include_embeddings,
        }
        return await self.client._make_request(
            "GET",
            f"documents/{str(id)}/entities",
            params=params,
            version="v3",
        )

    async def list_relationships(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        entity_names: Optional[list[str]] = None,
        relationship_types: Optional[list[str]] = None,
    ) -> dict:
        """
        List relationships extracted from a document.

        Args:
            id (Union[str, UUID]): ID of document to get relationships from
            offset (Optional[int]): Number of items to skip
            limit (Optional[int]): Max number of items to return
            entity_names (Optional[list[str]]): Filter by entity names
            relationship_types (Optional[list[str]]): Filter by relationship types

        Returns:
            dict: List of relationships and pagination info
        """
        params = {
            "offset": offset,
            "limit": limit,
        }
        if entity_names:
            params["entity_names"] = entity_names
        if relationship_types:
            params["relationship_types"] = relationship_types

        return await self.client._make_request(
            "GET",
            f"documents/{str(id)}/relationships",
            params=params,
            version="v3",
        )

    # async def extract(
    #     self,
    #     id: str | UUID,
    #     run_type: Optional[str] = None,
    #     run_with_orchestration: Optional[bool] = True,
    # ):
    #     data = {}

    #     if run_type:
    #         data["run_type"] = run_type
    #     if run_with_orchestration is not None:
    #         data["run_with_orchestration"] = str(run_with_orchestration)

    #     return await self.client._make_request(
    #         "POST",
    #         f"documents/{str(id)}/extract",
    #         params=data,
    #         version="v3",
    #     )

    # Be sure to put at bottom of the page...

    async def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedDocumentsResponse:
        """
        List documents with pagination.

        Args:
            ids (Optional[list[Union[str, UUID]]]): Optional list of document IDs to filter by
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of documents and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = [str(doc_id) for doc_id in ids]  # type: ignore

        return await self.client._make_request(
            "GET",
            "documents",
            params=params,
            version="v3",
        )

    async def search(
        self,
        query: str,
        search_mode: Optional[str | SearchMode] = "custom",
        search_settings: Optional[dict | SearchSettings] = None,
    ):
        """
        Conduct a vector and/or KG search.

        Args:
            query (str): The query to search for.
            search_settings (Optional[dict, SearchSettings]]): Vector search settings.

        Returns:
            CombinedSearchResponse: The search response.
        """
        # if search_mode and not isinstance(search_mode, str):
        #     search_mode = search_mode.value

        if search_settings and not isinstance(search_settings, dict):
            search_settings = search_settings.model_dump()
        data = {
            "query": query,
            "search_settings": search_settings,
        }
        if search_mode:
            data["search_mode"] = search_mode

        return await self.client._make_request(
            "POST",
            "documents/search",
            json=data,
            version="v3",
        )
