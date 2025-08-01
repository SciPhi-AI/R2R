import logging
import os
import zipfile
from datetime import datetime
from io import BytesIO
from typing import BinaryIO, Optional
from uuid import UUID

import boto3
from botocore.exceptions import ClientError

from core.base import FileConfig, FileProvider, R2RException

logger = logging.getLogger()


class S3FileProvider(FileProvider):
    """S3 implementation of the FileProvider."""

    def __init__(self, config: FileConfig):
        super().__init__(config)

        self.bucket_name = self.config.bucket_name or os.getenv(
            "S3_BUCKET_NAME"
        )
        aws_access_key_id = self.config.aws_access_key_id or os.getenv(
            "AWS_ACCESS_KEY_ID"
        )
        aws_secret_access_key = self.config.aws_secret_access_key or os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        )
        region_name = self.config.region_name or os.getenv("AWS_REGION")
        endpoint_url = self.config.endpoint_url or os.getenv("S3_ENDPOINT_URL")

        # Initialize S3 client
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
            endpoint_url=endpoint_url,
        )

    def _get_s3_key(self, document_id: UUID) -> str:
        """Generate a unique S3 key for a document."""
        return f"documents/{document_id}"

    async def initialize(self) -> None:
        """Initialize S3 bucket."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Using existing S3 bucket: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                logger.info(f"Creating S3 bucket: {self.bucket_name}")
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                logger.error(f"Error accessing S3 bucket: {e}")
                raise R2RException(
                    status_code=500,
                    message=f"Failed to initialize S3 bucket: {e}",
                ) from e

    async def store_file(
        self,
        document_id: UUID,
        file_name: str,
        file_content: BinaryIO,
        file_type: Optional[str] = None,
    ) -> None:
        """Store a file in S3."""
        try:
            # Generate S3 key
            s3_key = self._get_s3_key(document_id)

            # Upload to S3
            file_content.seek(0)  # Reset pointer to beginning
            self.s3_client.upload_fileobj(
                file_content,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    "ContentType": file_type or "application/octet-stream",
                    "Metadata": {
                        "filename": file_name,
                        "document_id": str(document_id),
                    },
                },
            )

        except Exception as e:
            logger.error(f"Error storing file in S3: {e}")
            raise R2RException(
                status_code=500, message=f"Failed to store file in S3: {e}"
            ) from e

    async def retrieve_file(
        self, document_id: UUID
    ) -> Optional[tuple[str, BinaryIO, int]]:
        """Retrieve a file from S3."""
        s3_key = self._get_s3_key(document_id)

        try:
            # Get file metadata from S3
            response = self.s3_client.head_object(
                Bucket=self.bucket_name, Key=s3_key
            )

            file_name = response.get("Metadata", {}).get(
                "filename", f"file-{document_id}"
            )
            file_size = response.get("ContentLength", 0)

            # Download file from S3
            file_content = BytesIO()
            self.s3_client.download_fileobj(
                self.bucket_name, s3_key, file_content
            )

            file_content.seek(0)  # Reset pointer to beginning
            return file_name, file_content, file_size

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ["NoSuchKey", "404"]:
                raise R2RException(
                    status_code=404,
                    message=f"File for document {document_id} not found",
                ) from e
            else:
                raise R2RException(
                    status_code=500,
                    message=f"Error retrieving file from S3: {e}",
                ) from e

    async def retrieve_files_as_zip(
        self,
        document_ids: Optional[list[UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[str, BinaryIO, int]:
        """Retrieve multiple files from S3 and return them as a zip file."""
        if not document_ids:
            raise R2RException(
                status_code=400,
                message="Document IDs must be provided for S3 file retrieval",
            )

        zip_buffer = BytesIO()

        with zipfile.ZipFile(
            zip_buffer, "w", zipfile.ZIP_DEFLATED
        ) as zip_file:
            for doc_id in document_ids:
                try:
                    # Get file information - note that retrieve_file won't return None here
                    # since any errors will raise exceptions
                    result = await self.retrieve_file(doc_id)
                    if result:
                        file_name, file_content, _ = result

                        # Read the content into a bytes object
                        if hasattr(file_content, "getvalue"):
                            content_bytes = file_content.getvalue()
                        else:
                            # For BinaryIO objects that don't have getvalue()
                            file_content.seek(0)
                            content_bytes = file_content.read()

                        # Add file to zip
                        zip_file.writestr(file_name, content_bytes)

                except R2RException as e:
                    if e.status_code == 404:
                        # Skip files that don't exist
                        logger.warning(
                            f"File for document {doc_id} not found, skipping"
                        )
                        continue
                    else:
                        raise

        zip_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"files_export_{timestamp}.zip"
        zip_size = zip_buffer.getbuffer().nbytes

        if zip_size == 0:
            raise R2RException(
                status_code=404,
                message="No files found for the specified document IDs",
            )

        return zip_filename, zip_buffer, zip_size

    async def delete_file(self, document_id: UUID) -> bool:
        """Delete a file from S3."""
        s3_key = self._get_s3_key(document_id)

        try:
            # Check if file exists first
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)

            # Delete from S3
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)

            return True

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ["NoSuchKey", "404"]:
                raise R2RException(
                    status_code=404,
                    message=f"File for document {document_id} not found",
                ) from e
            logger.error(f"Error deleting file from S3: {e}")
            raise R2RException(
                status_code=500, message=f"Failed to delete file from S3: {e}"
            ) from e

    async def get_files_overview(
        self,
        offset: int,
        limit: int,
        filter_document_ids: Optional[list[UUID]] = None,
        filter_file_names: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Get an overview of stored files.

        Note: Since S3 doesn't have native query capabilities like a database,
        this implementation works best when document IDs are provided.
        """
        results = []

        if filter_document_ids:
            # We can efficiently get specific files by document ID
            for doc_id in filter_document_ids:
                s3_key = self._get_s3_key(doc_id)
                try:
                    # Get metadata for this file
                    response = self.s3_client.head_object(
                        Bucket=self.bucket_name, Key=s3_key
                    )

                    file_info = {
                        "document_id": doc_id,
                        "file_name": response.get("Metadata", {}).get(
                            "filename", f"file-{doc_id}"
                        ),
                        "file_key": s3_key,
                        "file_size": response.get("ContentLength", 0),
                        "file_type": response.get("ContentType"),
                        "created_at": response.get("LastModified"),
                        "updated_at": response.get("LastModified"),
                    }

                    results.append(file_info)
                except ClientError:
                    # Skip files that don't exist
                    continue
        else:
            # This is a list operation on the bucket, which is less efficient
            # We list objects with the documents/ prefix
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix="documents/",
                )

                if "Contents" in response:
                    # Apply pagination manually
                    page_items = response["Contents"][offset : offset + limit]

                    for item in page_items:
                        # Extract document ID from the key
                        key = item["Key"]
                        doc_id_str = key.split("/")[-1]

                        try:
                            doc_id = UUID(doc_id_str)

                            # Get detailed metadata
                            obj_response = self.s3_client.head_object(
                                Bucket=self.bucket_name, Key=key
                            )

                            file_name = obj_response.get("Metadata", {}).get(
                                "filename", f"file-{doc_id}"
                            )

                            # Apply filename filter if provided
                            if (
                                filter_file_names
                                and file_name not in filter_file_names
                            ):
                                continue

                            file_info = {
                                "document_id": doc_id,
                                "file_name": file_name,
                                "file_key": key,
                                "file_size": item.get("Size", 0),
                                "file_type": obj_response.get("ContentType"),
                                "created_at": item.get("LastModified"),
                                "updated_at": item.get("LastModified"),
                            }

                            results.append(file_info)
                        except ValueError:
                            # Skip if the key doesn't contain a valid UUID
                            continue
            except ClientError as e:
                logger.error(f"Error listing files in S3 bucket: {e}")
                raise R2RException(
                    status_code=500,
                    message=f"Failed to list files from S3: {e}",
                ) from e

        if not results:
            raise R2RException(
                status_code=404,
                message="No files found with the given filters",
            )

        return results
