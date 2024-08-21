import json
import os
from contextlib import ExitStack
from typing import Optional, Union

from .models import ChunkingConfig
from uuid import UUID


class IngestionMethods:

    @staticmethod
    async def ingest_files(
        client,
        file_paths: list[str],
        document_ids: Optional[list[Union[str, UUID]]] = None,
        metadatas: Optional[list[dict]] = None,
        versions: Optional[list[str]] = None,
        chunking_settings: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        """
        Ingest files into your R2R deployment

        Args:
            file_paths (List[str]): List of file paths to ingest.
            metadatas (Optional[List[dict]]): List of metadata dictionaries for each file.
            document_ids (Optional[List[str]]): List of document IDs.
            versions (Optional[List[str]]): List of version strings for each file.
            chunking_settings (Optional[Union[dict, ChunkingConfig]]): Custom chunking configuration.

        Returns:
            dict: Ingestion results containing processed, failed, and skipped documents.
        """
        all_file_paths = []
        for path in file_paths:
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    all_file_paths.extend(
                        os.path.join(root, file) for file in files
                    )
            else:
                all_file_paths.append(path)

        with ExitStack() as stack:
            files = [
                (
                    "files",
                    (
                        os.path.basename(file),
                        stack.enter_context(open(file, "rb")),
                        "application/octet-stream",
                    ),
                )
                for file in all_file_paths
            ]

            data = {
                "metadatas": json.dumps(metadatas) if metadatas else None,
                "document_ids": (
                    json.dumps([str(doc_id) for doc_id in document_ids])
                    if document_ids
                    else None
                ),
                "versions": json.dumps(versions) if versions else None,
                "chunking_settings": (
                    json.dumps(
                        chunking_settings.model_dump()
                        if isinstance(chunking_settings, ChunkingConfig)
                        else chunking_settings
                    )
                    if chunking_settings
                    else None
                ),
            }
            return await client._make_request(
                "POST", "ingest_files", data=data, files=files
            )

    @staticmethod
    async def update_files(
        client,
        file_paths: list[str],
        document_ids: Optional[list[str]] = None,
        metadatas: Optional[list[dict]] = None,
        chunking_settings: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        """
        Update existing files in your R2R deployment.

        Args:
            file_paths (List[str]): List of file paths to update.
            document_ids (Optional[List[str]): An optional list of document IDs to update.
            metadatas (Optional[List[dict]]): List of updated metadata dictionaries for each file.
            chunking_settings (Optional[Union[dict, ChunkingConfig]]): Custom chunking configuration.

        Returns:
            dict: Update results containing processed, failed, and skipped documents.
        """
        if document_ids and len(file_paths) != len(document_ids):
            raise ValueError(
                "Number of file paths must match number of document IDs."
            )

        with ExitStack() as stack:
            files = [
                (
                    "files",
                    (
                        os.path.basename(file),
                        stack.enter_context(open(file, "rb")),
                        "application/octet-stream",
                    ),
                )
                for file in file_paths
            ]

            data = {
                "metadatas": json.dumps(metadatas) if metadatas else None,
                "document_ids": (
                    json.dumps([str(doc_id) for doc_id in document_ids])
                    if document_ids
                    else None
                ),
                "chunking_settings": (
                    json.dumps(
                        chunking_settings.model_dump()
                        if isinstance(chunking_settings, ChunkingConfig)
                        else chunking_settings
                    )
                    if chunking_settings
                    else None
                ),
            }
            return await client._make_request(
                "POST", "update_files", data=data, files=files
            )
