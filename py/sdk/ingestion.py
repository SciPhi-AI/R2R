import json
import os
from contextlib import ExitStack
from typing import Optional, Union
from uuid import UUID

from .models import ChunkingConfig


class IngestionMethods:

    @staticmethod
    async def ingest_files(
        client,
        file_paths: list[str],
        document_ids: Optional[list[Union[str, UUID]]] = None,
        metadatas: Optional[list[dict]] = None,
        chunking_config: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        """
        Ingest files into your R2R deployment

        Args:
            file_paths (List[str]): List of file paths to ingest.
            document_ids (Optional[List[str]]): List of document IDs.
            metadatas (Optional[List[dict]]): List of metadata dictionaries for each file.
            chunking_config (Optional[Union[dict, ChunkingConfig]]): Custom chunking configuration.

        Returns:
            dict: Ingestion results containing processed, failed, and skipped documents.
        """
        if document_ids is not None and len(file_paths) != len(document_ids):
            raise ValueError(
                "Number of file paths must match number of document IDs."
            )
        if metadatas is not None and len(file_paths) != len(metadatas):
            raise ValueError(
                "Number of metadatas must match number of document IDs."
            )
        if (
            chunking_config is not None
            and chunking_config is not ChunkingConfig
        ):
            # check if the provided dict maps to a ChunkingConfig
            ChunkingConfig(**chunking_config)

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
                "chunking_config": (
                    json.dumps(
                        chunking_config.model_dump()
                        if isinstance(chunking_config, ChunkingConfig)
                        else chunking_config
                    )
                    if chunking_config
                    else None
                ),
            }
            return await client._make_request(
                "POST", "ingest_files", data=data, files=files
            )

    @staticmethod
    async def retry_ingest_files(
        client,
        document_ids: list[Union[str, UUID]],
    ) -> dict:
        """
        Retry ingestion for failed documents.

        Args:
            document_ids (List[Union[str, UUID]]): List of document IDs to retry.

        Returns:
            dict: Retry results containing processed, failed, and skipped documents.
        """
        return await client._make_request(
            "POST",
            "retry_ingest_files",
            data={"document_ids": [str(doc_id) for doc_id in document_ids]},
        )

    @staticmethod
    async def update_files(
        client,
        file_paths: list[str],
        document_ids: Optional[list[Union[str, UUID]]] = None,
        metadatas: Optional[list[dict]] = None,
        chunking_config: Optional[Union[dict, ChunkingConfig]] = None,
    ) -> dict:
        """
        Update existing files in your R2R deployment.

        Args:
            file_paths (List[str]): List of file paths to update.
            document_ids (List[str]): List of document IDs to update.
            metadatas (Optional[List[dict]]): List of updated metadata dictionaries for each file.
            chunking_config (Optional[Union[dict, ChunkingConfig]]): Custom chunking configuration.

        Returns:
            dict: Update results containing processed, failed, and skipped documents.
        """
        if document_ids is not None and len(file_paths) != len(document_ids):
            raise ValueError(
                "Number of file paths must match number of document IDs."
            )
        if metadatas is not None and len(file_paths) != len(metadatas):
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

            data = {}
            if document_ids:
                data["document_ids"] = json.dumps(
                    [str(doc_id) for doc_id in document_ids]
                )
            if metadatas:
                data["metadatas"] = json.dumps(metadatas)
            if chunking_config:
                data["chunking_config"] = (
                    chunking_config.model_dump()
                    if isinstance(chunking_config, ChunkingConfig)
                    else chunking_config
                )

            return await client._make_request(
                "POST", "update_files", data=data, files=files
            )
