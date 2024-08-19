import json
import os
from contextlib import ExitStack
from typing import List, Optional, Union

from r2r.base import ChunkingConfig


class IngestionMethods:

    @staticmethod
    async def ingest_files(
        client,
        file_paths: List[str],
        metadatas: Optional[List[dict]] = None,
        document_ids: Optional[List[str]] = None,
        versions: Optional[List[str]] = None,
        chunking_config_override: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        """
        Ingest files into your R2R deployment

        Args:
            file_paths (List[str]): List of file paths to ingest.
            metadatas (Optional[List[dict]]): List of metadata dictionaries for each file.
            document_ids (Optional[List[str]]): List of document IDs.
            versions (Optional[List[str]]): List of version strings for each file.
            chunking_config_override (Optional[Union[dict, ChunkingConfig]]): Custom chunking configuration.

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
                "chunking_config_override": (
                    json.dumps(
                        chunking_config_override.model_dump()
                        if isinstance(chunking_config_override, ChunkingConfig)
                        else chunking_config_override
                    )
                    if chunking_config_override
                    else None
                ),
            }

            return await client._make_request(
                "POST", "ingest_files", data=data, files=files
            )

    @staticmethod
    async def update_files(
        client,
        file_paths: List[str],
        document_ids: List[str],
        metadatas: Optional[List[dict]] = None,
        chunking_config_override: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        """
        Update existing files in your R2R deployment.

        Args:
            file_paths (List[str]): List of file paths to update.
            document_ids (List[str]): List of document IDs to update.
            metadatas (Optional[List[dict]]): List of updated metadata dictionaries for each file.
            chunking_config_override (Optional[Union[dict, ChunkingConfig]]): Custom chunking configuration.

        Returns:
            dict: Update results containing processed, failed, and skipped documents.
        """
        if len(file_paths) != len(document_ids):
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
                "document_ids": json.dumps(document_ids),
                "metadatas": json.dumps(metadatas) if metadatas else None,
                "chunking_config_override": (
                    json.dumps(
                        chunking_config_override.dict()
                        if isinstance(chunking_config_override, ChunkingConfig)
                        else chunking_config_override
                    )
                    if chunking_config_override
                    else None
                ),
            }

            return await client._make_request(
                "POST", "update_files", data=data, files=files
            )
