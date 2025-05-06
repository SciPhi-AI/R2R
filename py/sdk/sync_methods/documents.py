import json
import logging
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

import requests

from shared.api.models import (
    WrappedBooleanResponse,
    WrappedChunksResponse,
    WrappedCollectionsResponse,
    WrappedDocumentResponse,
    WrappedDocumentSearchResponse,
    WrappedDocumentsResponse,
    WrappedEntitiesResponse,
    WrappedGenericMessageResponse,
    WrappedIngestionResponse,
    WrappedRelationshipsResponse,
)

from ..models import (
    GraphCreationSettings,
    IngestionMode,
    SearchMode,
    SearchSettings,
)

logger = logging.getLogger()


class DocumentsSDK:
    """SDK for interacting with documents in the v3 API."""

    def __init__(self, client):
        self.client = client

    def create(
        self,
        file_path: Optional[str] = None,
        raw_text: Optional[str] = None,
        chunks: Optional[list[str]] = None,
        id: Optional[str | UUID] = None,
        ingestion_mode: Optional[IngestionMode | str] = None,
        collection_ids: Optional[list[str | UUID]] = None,
        metadata: Optional[dict[str, Any]] = None,
        ingestion_config: Optional[dict | IngestionMode] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedIngestionResponse:
        """Create a new document from either a file, raw text, or chunks.

        Note: Access control might apply based on user limits (max documents, chunks, collections).

        Args:
            file_path (Optional[str]): The path to the file to upload, if any.
            raw_text (Optional[str]): Raw text content to upload, if no file path is provided.
            chunks (Optional[list[str]]): Pre-processed text chunks to ingest.
            id (Optional[str | UUID]): Optional ID to assign to the document.
            ingestion_mode (Optional[IngestionMode | str]): The ingestion mode preset ('hi-res', 'ocr', 'fast', 'custom'). Defaults to 'custom'.
            collection_ids (Optional[list[str | UUID]]): Collection IDs to associate. Defaults to user's default collection if None.
            metadata (Optional[dict]): Optional metadata to assign to the document.
            ingestion_config (Optional[dict | IngestionMode]): Optional ingestion config or preset mode enum. Used when ingestion_mode='custom'.
            run_with_orchestration (Optional[bool]): Whether to run with orchestration (default: True).

        Returns:
            WrappedIngestionResponse
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

        data: dict[str, Any] = {}
        files = None

        if id:
            data["id"] = str(id)
        if metadata:
            data["metadata"] = json.dumps(metadata)
        if ingestion_config:
            if isinstance(ingestion_config, IngestionMode):
                ingestion_config = {"mode": ingestion_config.value}
            app_config: dict[str, Any] = (
                {}
                if isinstance(ingestion_config, dict)
                else ingestion_config["app"]
            )
            ingestion_config = dict(ingestion_config)
            ingestion_config["app"] = app_config
            data["ingestion_config"] = json.dumps(ingestion_config)
        if collection_ids:
            collection_ids = [
                str(collection_id) for collection_id in collection_ids
            ]
            data["collection_ids"] = json.dumps(collection_ids)
        if run_with_orchestration is not None:
            data["run_with_orchestration"] = str(run_with_orchestration)
        if ingestion_mode is not None:
            data["ingestion_mode"] = (
                ingestion_mode.value
                if isinstance(ingestion_mode, IngestionMode)
                else ingestion_mode
            )
        if file_path:
            # Check if file exists before opening
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found at path: {file_path}")
            # Create a new file instance that will remain open during the request
            file_instance = open(file_path, "rb")
            # Extract filename for the multipart form
            filename = os.path.basename(file_path)
            files = [
                (
                    "file",
                    (
                        filename,
                        file_instance,
                        "application/octet-stream",
                    ),  # Use actual filename
                )
            ]
            try:
                # _make_request should handle multipart/form-data when files are present
                response_dict = self.client._make_request(
                    "POST",
                    "documents",
                    data=data,  # Form fields
                    files=files,  # File part
                    version="v3",
                )
            finally:
                # Ensure we close the file after the request is complete
                file_instance.close()
        elif raw_text:
            data["raw_text"] = raw_text
            response_dict = self.client._make_request(
                "POST",
                "documents",
                data=data,  # Form fields
                version="v3",
            )
        else:  # chunks
            # Ensure chunks is not None here, checked at the start
            data["chunks"] = json.dumps(chunks)
            response_dict = self.client._make_request(
                "POST",
                "documents",
                data=data,  # Form fields
                version="v3",
            )

        return WrappedIngestionResponse(**response_dict)

    def append_metadata(
        self,
        id: str | UUID,
        metadata: list[dict[str, Any]],  # More specific type hint
    ) -> WrappedDocumentResponse:
        """Append metadata to a document.

        Note: Users can typically only modify metadata for documents they own. Superusers may have broader access.

        Args:
            id (str | UUID): ID of document to append metadata to
            metadata (list[dict]): Metadata entries (key-value pairs) to append

        Returns:
            WrappedDocumentResponse
        """
        # PATCH expects JSON body
        response_dict = self.client._make_request(
            "PATCH",
            f"documents/{str(id)}/metadata",
            json=metadata,  # Send as JSON body
            version="v3",
        )

        return WrappedDocumentResponse(**response_dict)

    def replace_metadata(
        self,
        id: str | UUID,
        metadata: list[dict[str, Any]],  # More specific type hint
    ) -> WrappedDocumentResponse:
        """Replace metadata for a document. This overwrites all existing metadata.

        Note: Users can typically only replace metadata for documents they own. Superusers may have broader access.

        Args:
            id (str | UUID): ID of document to replace metadata for
            metadata (list[dict]): The new list of metadata entries (key-value pairs)

        Returns:
            WrappedDocumentResponse
        """
        # PUT expects JSON body
        response_dict = self.client._make_request(
            "PUT",
            f"documents/{str(id)}/metadata",
            json=metadata,  # Send as JSON body
            version="v3",
        )

        return WrappedDocumentResponse(**response_dict)

    def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedDocumentResponse:
        """Get details for a specific document by ID.

        Note: Users can only retrieve documents they own or have access to through collections. Superusers can retrieve any document.

        Args:
            id (str | UUID): ID of document to retrieve

        Returns:
            WrappedDocumentResponse
        """
        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(id)}",
            version="v3",
        )
        # TODO: Add check for non-dict response if _make_request can return raw bytes
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )

        return WrappedDocumentResponse(**response_dict)

    def download(
        self,
        id: str | UUID,
    ) -> BytesIO:
        """Download a document's original file content.

        Note: Users can only download documents they own or have access to through collections.

        Args:
            id (str | UUID): ID of document to download

        Returns:
            BytesIO: In-memory bytes buffer containing the document's file content.
        """
        response = self.client._make_request(
            "GET",
            f"documents/{str(id)}/download",
            version="v3",
        )
        if not isinstance(response, BytesIO):
            raise ValueError("Expected BytesIO response")
        return response

    def download_zip(
        self,
        document_ids: Optional[list[str | UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        output_path: Optional[str | Path] = None,
    ) -> Optional[BytesIO]:
        """Download multiple documents as a zip file.

        Note: Access control applies. Non-superusers might be restricted and may need to provide document_ids.

        Args:
            document_ids (Optional[list[str | UUID]]): IDs to include. May be required for non-superusers.
            start_date (Optional[datetime]): Filter documents created on or after this date.
            end_date (Optional[datetime]): Filter documents created on or before this date.
            output_path (Optional[str | Path]): If provided, save the zip file to this path and return None. Otherwise, return BytesIO.

        Returns:
            Optional[BytesIO]: BytesIO object with zip content if output_path is None, else None.
        """
        params: dict[str, Any] = {}
        if document_ids:
            # Ensure IDs are strings for the query parameter
            params["document_ids"] = [str(doc_id) for doc_id in document_ids]
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()

        response_bytes = self.client._make_request(
            "GET",
            "documents/download_zip",
            params=params,
            version="v3",
            # headers={"Accept": "application/zip"} # Might be needed
        )

        if not isinstance(response_bytes, BytesIO):
            raise ValueError("Expected BytesIO response")

        if output_path:
            output_path_obj = Path(output_path)
            # Ensure parent directory exists
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path_obj, "wb") as f:
                f.write(response_bytes.getvalue())
            return None  # Return None when saving to file

        return response_bytes  # Return BytesIO otherwise

    def export(
        self,
        output_path: str | Path,
        columns: Optional[list[str]] = None,
        filters: Optional[dict[str, Any]] = None,
        include_header: bool = True,
    ) -> None:
        """Export documents metadata to a CSV file, streaming the results directly to disk.

        Note: This operation is typically restricted to superusers.

        Args:
            output_path (str | Path): Local path where the CSV file should be saved.
            columns (Optional[list[str]]): Specific columns to export. If None, exports default columns.
            filters (Optional[dict]): Optional filters to apply when selecting documents.
            include_header (bool): Whether to include column headers in the CSV (default: True).

        Returns:
            None
        """
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(
            parents=True, exist_ok=True
        )  # Ensure directory exists

        request_data: dict[str, Any] = {"include_header": include_header}
        if columns:
            request_data["columns"] = columns
        if filters:
            request_data["filters"] = (
                filters  # Assuming filters are already JSON-serializable dict
            )

        # Use requests directly for streaming response to file
        # Get auth header and base URL from the client instance
        auth_header = self.client._get_auth_header()
        base_url = self.client.base_url

        try:
            with requests.post(
                f"{base_url}/v3/documents/export",
                json=request_data,  # Send options as JSON body
                headers={
                    "Accept": "text/csv",
                    **auth_header,  # Include authentication
                },
                stream=True,  # Enable streaming response
                timeout=self.client.timeout,  # Use client timeout
            ) as response:
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

                with open(output_path_obj, "wb") as f:
                    for chunk in response.iter_content(
                        chunk_size=8192
                    ):  # Stream in chunks
                        if chunk:  # Filter out keep-alive new chunks
                            f.write(chunk)

        except requests.exceptions.RequestException as e:
            # Handle potential network errors, timeouts, etc.
            raise ConnectionError(f"Export request failed: {e}") from e
        except Exception as e:
            # Catch other potential errors during file writing etc.
            raise RuntimeError(f"An error occurred during export: {e}") from e

    def export_entities(
        self,
        id: str | UUID,
        output_path: str | Path,
        columns: Optional[list[str]] = None,
        filters: Optional[dict[str, Any]] = None,
        include_header: bool = True,
    ) -> None:
        """Export entities for a specific document to a CSV file, streaming to disk.

        Note: Access control (superuser/owner) applies.

        Args:
            id (str | UUID): The ID of the document whose entities to export.
            output_path (str | Path): Local path where the CSV file should be saved.
            columns (Optional[list[str]]): Specific columns to export.
            filters (Optional[dict]): Optional filters to apply.
            include_header (bool): Whether to include column headers (default: True).

        Returns:
            None
        """
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        request_data: dict[str, Any] = {"include_header": include_header}
        if columns:
            request_data["columns"] = columns
        if filters:
            request_data["filters"] = filters

        auth_header = self.client._get_auth_header()
        base_url = self.client.base_url
        doc_id_str = str(id)

        try:
            # ID goes into the URL path
            with requests.post(
                f"{base_url}/v3/documents/{doc_id_str}/entities/export",
                json=request_data,  # Options in JSON body
                headers={
                    "Accept": "text/csv",
                    **auth_header,
                },
                stream=True,
                timeout=self.client.timeout,
            ) as response:
                response.raise_for_status()
                with open(output_path_obj, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
        except requests.exceptions.RequestException as e:
            raise ConnectionError(
                f"Export entities request failed: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"An error occurred during entity export: {e}"
            ) from e

    def export_relationships(
        self,
        id: str | UUID,
        output_path: str | Path,
        columns: Optional[list[str]] = None,
        filters: Optional[dict[str, Any]] = None,
        include_header: bool = True,
    ) -> None:
        """Export relationships for a specific document to a CSV file, streaming to disk.

        Note: Access control (superuser/owner) applies.

        Args:
            id (str | UUID): The ID of the document whose relationships to export.
            output_path (str | Path): Local path where the CSV file should be saved.
            columns (Optional[list[str]]): Specific columns to export.
            filters (Optional[dict]): Optional filters to apply.
            include_header (bool): Whether to include column headers (default: True).

        Returns:
            None
        """
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        request_data: dict[str, Any] = {"include_header": include_header}
        if columns:
            request_data["columns"] = columns
        if filters:
            request_data["filters"] = filters

        auth_header = self.client._get_auth_header()
        base_url = self.client.base_url
        doc_id_str = str(id)

        try:
            # ID goes into the URL path
            with requests.post(
                f"{base_url}/v3/documents/{doc_id_str}/relationships/export",
                json=request_data,  # Options in JSON body
                headers={
                    "Accept": "text/csv",
                    **auth_header,
                },
                stream=True,
                timeout=self.client.timeout,
            ) as response:
                response.raise_for_status()
                with open(output_path_obj, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
        except requests.exceptions.RequestException as e:
            raise ConnectionError(
                f"Export relationships request failed: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"An error occurred during relationship export: {e}"
            ) from e

    def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Delete a specific document by ID. This also deletes associated chunks.

        Note: Users can typically only delete documents they own. Superusers may have broader access.

        Args:
            id (str | UUID): ID of document to delete

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE",
            f"documents/{str(id)}",
            version="v3",
        )
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )
        return WrappedBooleanResponse(**response_dict)

    def list_chunks(
        self,
        id: str | UUID,
        include_vectors: Optional[bool] = False,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedChunksResponse:
        """Get chunks for a specific document.

        Note: Users can only access chunks from documents they own or have access to through collections.

        Args:
            id (str | UUID): ID of document to retrieve chunks for.
            include_vectors (Optional[bool]): Whether to include vector embeddings (default: False).
            offset (int, optional): Number of objects to skip. Defaults to 0.
            limit (int, optional): Max number of objects to return (1-1000). Defaults to 100.

        Returns:
            WrappedChunksResponse
        """
        params = {
            "offset": offset,
            "limit": limit,
            "include_vectors": include_vectors,  # Use the parameter name matching the router
        }
        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(id)}/chunks",
            params=params,
            version="v3",
        )
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )
        return WrappedChunksResponse(**response_dict)

    def list_collections(
        self,
        id: str | UUID,
        # include_vectors: Optional[bool] = False, # Removed unused parameter
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedCollectionsResponse:
        """list collections associated with a specific document.

        Note: This endpoint might be restricted to superusers depending on API implementation. Check API documentation.

        Args:
            id (str | UUID): ID of document to retrieve collections for.
            offset (int, optional): Number of objects to skip. Defaults to 0.
            limit (int, optional): Max number of objects to return (1-1000). Defaults to 100.

        Returns:
            WrappedCollectionsResponse
        """
        params = {
            "offset": offset,
            "limit": limit,
            # No include_vectors here
        }

        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(id)}/collections",
            params=params,
            version="v3",
        )
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )
        return WrappedCollectionsResponse(**response_dict)

    def delete_by_filter(
        self,
        filters: dict[str, Any],
    ) -> WrappedBooleanResponse:
        """Delete documents based on metadata filters.

        Note: For non-superusers, deletion is implicitly limited to documents owned by the user, in addition to the provided filters.

        Args:
            filters (dict): Filters to apply (e.g., `{"metadata.year": {"$lt": 2020}}`).

        Returns:
            WrappedBooleanResponse
        """
        # Send filters as JSON body for DELETE request
        response_dict = self.client._make_request(
            "DELETE",
            "documents/by-filter",
            json=filters,  # Use json parameter for request body
            version="v3",
        )
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )
        return WrappedBooleanResponse(**response_dict)

    def extract(
        self,
        id: str | UUID,
        settings: Optional[dict | GraphCreationSettings] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedGenericMessageResponse:
        """Triggers the extraction of entities and relationships from a document.

        Note: Users typically need to own the document. This is often an async process.

        Args:
            id (str | UUID): ID of document to extract from.
            settings (Optional[dict | GraphCreationSettings]): Settings for extraction process.
            run_with_orchestration (Optional[bool]): Whether to run with orchestration (default: True).

        Returns:
            WrappedGenericMessageResponse: Indicating task status.
        """
        data: dict[str, Any] = {}
        if settings:
            # Convert settings model to dict if necessary
            if hasattr(settings, "model_dump"):
                data["settings"] = settings.model_dump(exclude_unset=True)
            elif isinstance(settings, dict):
                data["settings"] = settings
            else:
                raise TypeError("settings must be a dict or Pydantic model")
        if run_with_orchestration is not None:
            # Send boolean directly in JSON body
            data["run_with_orchestration"] = run_with_orchestration

        # POST expects JSON body for settings/orchestration flag
        response_dict = self.client._make_request(
            "POST",
            f"documents/{str(id)}/extract",
            json=data,  # Send data as JSON body
            version="v3",
        )
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )
        return WrappedGenericMessageResponse(**response_dict)

    def list_entities(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        include_embeddings: Optional[
            bool
        ] = False,  # Renamed from includeVectors
    ) -> WrappedEntitiesResponse:
        """list entities extracted from a document.

        Note: Users can only access entities from documents they own or have access to through collections.

        Args:
            id (str | UUID): ID of document to get entities from.
            offset (Optional[int]): Number of items to skip (default: 0).
            limit (Optional[int]): Max number of items to return (1-1000, default: 100).
            include_embeddings (Optional[bool]): Whether to include embeddings (default: False).

        Returns:
            WrappedEntitiesResponse
        """
        params = {
            "offset": offset,
            "limit": limit,
            "include_embeddings": include_embeddings,  # Use router param name
        }
        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(id)}/entities",
            params=params,
            version="v3",
        )
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )
        return WrappedEntitiesResponse(**response_dict)

    def list_relationships(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        entity_names: Optional[list[str]] = None,
        relationship_types: Optional[list[str]] = None,
        # include_embeddings param does not exist on router for relationships
    ) -> WrappedRelationshipsResponse:
        """list relationships extracted from a document.

        Note: Users can only access relationships from documents they own or have access to through collections.

        Args:
            id (str | UUID): ID of document to get relationships from.
            offset (Optional[int]): Number of items to skip (default: 0).
            limit (Optional[int]): Max number of items to return (1-1000, default: 100).
            entity_names (Optional[list[str]]): Filter by entity names.
            relationship_types (Optional[list[str]]): Filter by relationship types.

        Returns:
            WrappedRelationshipsResponse
        """
        params: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
        }
        if entity_names:
            params["entity_names"] = entity_names
        if relationship_types:
            params["relationship_types"] = relationship_types

        response_dict = self.client._make_request(
            "GET",
            f"documents/{str(id)}/relationships",
            params=params,
            version="v3",
        )
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )
        return WrappedRelationshipsResponse(**response_dict)

    def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
        include_summary_embeddings: Optional[bool] = False,
        owner_only: Optional[bool] = False,
    ) -> WrappedDocumentsResponse:
        """list documents with pagination.

        Note: Regular users will only see documents they own or have access to through collections. Superusers can see all documents.

        Args:
            ids (Optional[list[str | UUID]]): Optional list of document IDs to filter by.
            offset (int, optional): Number of objects to skip. Defaults to 0.
            limit (int, optional): Max number of objects to return (1-1000). Defaults to 100.
            include_summary_embeddings (Optional[bool]): Whether to include summary embeddings (default: False).
            owner_only (Optional[bool]): If true, only returns documents owned by the user, not all accessible documents.

        Returns:
            WrappedDocumentsResponse
        """
        params: dict[str, Any] = {
            "offset": offset,
            "limit": limit,
            "include_summary_embeddings": include_summary_embeddings,
            "owner_only": owner_only,
        }
        if ids:
            params["ids"] = [str(doc_id) for doc_id in ids]

        response_dict = self.client._make_request(
            "GET",
            "documents",
            params=params,
            version="v3",
        )
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )
        return WrappedDocumentsResponse(**response_dict)

    def search(
        self,
        query: str,
        search_mode: Optional[
            str | SearchMode
        ] = SearchMode.custom,  # Use enum
        search_settings: Optional[
            dict | SearchSettings
        ] = None,  # Use SearchSettings model if defined
    ) -> WrappedDocumentSearchResponse:
        """Conduct a search query on document summaries.

        Note: Access control (based on user ownership/collection access) is applied to search results.

        Args:
            query (str): The search query.
            search_mode (Optional[str | SearchMode]): Search mode ('basic', 'advanced', 'custom'). Defaults to 'custom'.
            search_settings (Optional[dict | SearchSettings]): Search settings (filters, limits, hybrid options, etc.).

        Returns:
            WrappedDocumentSearchResponse
        """
        settings_dict = {}
        if search_settings:
            if isinstance(search_settings, SearchSettings):
                settings_dict = search_settings.model_dump(exclude_unset=True)
            elif isinstance(search_settings, dict):
                settings_dict = search_settings
            else:
                raise TypeError(
                    "search_settings must be a dict or SearchSettings model"
                )

        request_data: dict[str, Any] = {
            "query": query,
            "search_mode": search_mode.value
            if isinstance(search_mode, SearchMode)
            else search_mode,
            "search_settings": settings_dict,
        }

        # POST request with JSON body
        response_dict = self.client._make_request(
            "POST",
            "documents/search",
            json=request_data,
            version="v3",
        )
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )
        return WrappedDocumentSearchResponse(**response_dict)

    def deduplicate(
        self,
        id: str | UUID,
        settings: Optional[
            dict | GraphCreationSettings
        ] = None,  # Use GraphCreationSettings if defined
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedGenericMessageResponse:
        """Triggers the deduplication of entities within a document.

        Note: Users typically need to own the document. This is often an async process.

        Args:
            id (str | UUID): ID of document to deduplicate entities for.
            settings (Optional[dict | GraphCreationSettings]): Settings for deduplication process.
            run_with_orchestration (Optional[bool]): Whether to run with orchestration (default: True).

        Returns:
            WrappedGenericMessageResponse: Indicating task status.
        """
        data: dict[str, Any] = {}
        if settings:
            if hasattr(settings, "model_dump"):
                data["settings"] = settings.model_dump(exclude_unset=True)
            elif isinstance(settings, dict):
                data["settings"] = settings
            else:
                raise TypeError("settings must be a dict or Pydantic model")

        if run_with_orchestration is not None:
            data["run_with_orchestration"] = run_with_orchestration

        # POST expects JSON body for settings/orchestration flag
        response_dict = self.client._make_request(
            "POST",
            f"documents/{str(id)}/deduplicate",
            json=data,  # Send data as JSON body
            version="v3",
        )
        if not isinstance(response_dict, dict):
            raise ValueError(
                f"Expected dict response, got {type(response_dict)}"
            )
        return WrappedGenericMessageResponse(**response_dict)
