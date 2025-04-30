import logging
from datetime import datetime
from io import BytesIO
from typing import BinaryIO, Optional
from uuid import UUID

# import boto3
# from botocore.exceptions import ClientError
from core.base import FileConfig, FileProvider

logger = logging.getLogger()


class S3FileProvider(FileProvider):
    """S3 implementation of the FileProvider."""

    def __init__(
        self,
        config: FileConfig,
        database_provider=None,  # PostgresDatabaseProvider
    ):
        super().__init__(config)

    def _get_table_name(self):
        pass

    def _get_s3_key(self):
        pass

    async def initialize(self):
        """Initialize S3 bucket and metadata table."""
        pass

    async def upsert_file(
        self,
        document_id: UUID,
        file_name: str,
        s3_key: str,
        file_size: int,
        file_type: Optional[str] = None,
    ):
        pass

    async def store_file(
        self,
        document_id: UUID,
        file_name: str,
        file_content: BytesIO,
        file_type: Optional[str] = None,
    ) -> None:
        pass

    async def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        pass

    async def retrieve_files_as_zip(
        self,
        document_ids: Optional[list[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ):
        pass

    async def delete_file(self, document_id: UUID):
        pass

    async def get_files_overview(
        self,
        offset: int,
        limit: int,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
    ):
        pass
