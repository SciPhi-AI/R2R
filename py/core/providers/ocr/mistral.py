import logging
import os
from typing import Any

from mistralai import Mistral
from mistralai.models import OCRResponse

from core.base.providers.ocr import OCRConfig, OCRProvider

logger = logging.getLogger()


class MistralOCRProvider(OCRProvider):
    def __init__(self, config: OCRConfig) -> None:
        if not isinstance(config, OCRConfig):
            raise ValueError(
                f"MistralOCRProvider must be initialized with a OCRConfig. Got: {config} with type {type(config)}"
            )
        super().__init__(config)
        self.config: OCRConfig = config

        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            logger.warning(
                "MISTRAL_API_KEY not set in environment, if you plan to use Mistral OCR, please set it."
            )

        self.mistral = Mistral(api_key=api_key)
        self.model = config.model or "mistral-ocr-latest"

    async def _execute_task(self, task: dict[str, Any]) -> OCRResponse:
        """Execute OCR task asynchronously."""
        document = task.get("document")
        include_image_base64 = task.get("include_image_base64", False)

        # Process through Mistral OCR API
        return await self.mistral.ocr.process_async(
            model=self.model,
            document=document,  # type: ignore
            include_image_base64=include_image_base64,
        )

    def _execute_task_sync(self, task: dict[str, Any]) -> OCRResponse:
        """Execute OCR task synchronously."""
        document = task.get("document")
        include_image_base64 = task.get("include_image_base64", False)

        # Process through Mistral OCR API
        return self.mistral.ocr.process(  # type: ignore
            model=self.model,
            document=document,  # type: ignore
            include_image_base64=include_image_base64,
        )

    async def upload_file(
        self,
        file_path: str | None = None,
        file_content: bytes | None = None,
        file_name: str | None = None,
    ) -> Any:
        """
        Upload a file for OCR processing.

        Args:
            file_path: Path to the file to upload
            file_content: Binary content of the file
            file_name: Name of the file (required if file_content is provided)

        Returns:
            The uploaded file object
        """
        if file_path:
            file_name = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                file_content = f.read()
        elif not file_content or not file_name:
            raise ValueError(
                "Either file_path or (file_content and file_name) must be provided"
            )

        return await self.mistral.files.upload_async(
            file={
                "file_name": file_name,
                "content": file_content,
            },
            purpose="ocr",
        )

    async def process_file(
        self, file_id: str, include_image_base64: bool = False
    ) -> OCRResponse:
        """
        Process a previously uploaded file using its file ID.

        Args:
            file_id: ID of the file to process
            include_image_base64: Whether to include image base64 in the response

        Returns:
            OCR response object
        """
        # Get the signed URL for the file
        signed_url = await self.mistral.files.get_signed_url_async(
            file_id=file_id
        )

        # Create the document data
        document = {
            "type": "document_url",
            "document_url": signed_url.url,
        }

        # Process the document
        task = {
            "document": document,
            "include_image_base64": include_image_base64,
        }

        return await self._execute_with_backoff_async(task)

    async def process_url(
        self,
        url: str,
        is_image: bool = False,
        include_image_base64: bool = False,
    ) -> OCRResponse:
        """
        Process a document or image from a URL.

        Args:
            url: URL of the document or image
            is_image: Whether the URL points to an image
            include_image_base64: Whether to include image base64 in the response

        Returns:
            OCR response object
        """
        # Create the document data
        document_type = "image_url" if is_image else "document_url"
        document = {
            "type": document_type,
            document_type: url,
        }

        # Process the document
        task = {
            "document": document,
            "include_image_base64": include_image_base64,
        }

        return await self._execute_with_backoff_async(task)

    async def process_pdf(
        self, file_path: str | None = None, file_content: bytes | None = None
    ) -> OCRResponse:
        """
        Upload and process a PDF file in one step.

        Args:
            file_path: Path to the PDF file
            file_content: Binary content of the PDF file

        Returns:
            OCR response object
        """
        # Upload the file
        if file_path:
            file_name = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                file_content = f.read()
        elif not file_content:
            raise ValueError(
                "Either file_path or file_content must be provided"
            )

        file_name = file_name if file_path else "document.pdf"

        uploaded_file = await self.upload_file(
            file_name=file_name, file_content=file_content
        )

        # Process the uploaded file
        return await self.process_file(uploaded_file.id)
