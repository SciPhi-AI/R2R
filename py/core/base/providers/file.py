import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from io import BytesIO
from typing import BinaryIO, Optional
from uuid import UUID

from .base import Provider, ProviderConfig

logger = logging.getLogger()


class FileConfig(ProviderConfig):
    """
    Configuration for file storage providers.
    """

    provider: Optional[str] = None

    # S3-specific configuration
    bucket_name: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    region_name: Optional[str] = None
    endpoint_url: Optional[str] = None

    @property
    def supported_providers(self) -> list[str]:
        """
        List of supported file storage providers.
        """
        return [
            "postgres",
            "s3",
        ]

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Unsupported file provider: {self.provider}")

        if self.provider == "s3" and (
            not self.bucket_name and not os.getenv("S3_BUCKET_NAME")
        ):
            raise ValueError(
                "S3 bucket name is required when using S3 provider"
            )


class FileProvider(Provider, ABC):
    """
    Base abstract class for file storage providers.
    """

    def __init__(self, config: FileConfig):
        if not isinstance(config, FileConfig):
            raise ValueError(
                "FileProvider must be initialized with a `FileConfig`."
            )
        super().__init__(config)
        self.config: FileConfig = config

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the file provider."""
        pass

    @abstractmethod
    async def store_file(
        self,
        document_id: UUID,
        file_name: str,
        file_content: BytesIO,
        file_type: Optional[str] = None,
    ) -> None:
        """Store a file."""
        pass

    @abstractmethod
    async def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        """Retrieve a file."""
        pass

    @abstractmethod
    async def retrieve_files_as_zip(
        self,
        document_ids: Optional[list[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[str, BinaryIO, int]:
        """Retrieve multiple files as a zip."""
        pass

    @abstractmethod
    async def delete_file(self, document_id: UUID) -> bool:
        """Delete a file."""
        pass

    @abstractmethod
    async def get_files_overview(
        self,
        offset: int,
        limit: int,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
    ) -> list[dict]:
        """Get an overview of stored files."""
        pass
