# type: ignore
import asyncio
import base64
import logging
import os
import string
import tempfile
import unicodedata
import uuid
from io import BytesIO
from typing import AsyncGenerator

import aiofiles
from pdf2image import convert_from_path

from core.base.abstractions import GenerationConfig
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)

logger = logging.getLogger()


class VLMPDFParser(AsyncParser[str | bytes]):
    """A parser for PDF documents using vision models for page processing."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.vision_prompt_text = None

        try:
            from litellm import supports_vision

            self.supports_vision = supports_vision
        except ImportError:
            logger.error("Failed to import LiteLLM vision support")
            raise ImportError(
                "Please install the `litellm` package to use the VLMPDFParser."
            )

    def _create_temp_dir(self) -> str:
        """Create a unique temporary directory for PDF processing."""
        # Create a unique directory name using UUID
        unique_id = str(uuid.uuid4())
        temp_base = tempfile.gettempdir()
        temp_dir = os.path.join(temp_base, f"pdf_images_{unique_id}")
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir

    async def convert_pdf_to_images(
        self, pdf_path: str, temp_dir: str
    ) -> list[str]:
        """Convert PDF pages to images asynchronously."""
        options = {
            "pdf_path": pdf_path,
            "output_folder": temp_dir,
            "dpi": 300,  # Configurable via config if needed
            "fmt": "jpeg",
            "thread_count": 4,
            "paths_only": True,
        }
        try:
            image_paths = await asyncio.to_thread(convert_from_path, **options)
            return image_paths
        except Exception as err:
            logger.error(f"Error converting PDF to images: {err}")
            raise

    async def process_page(
        self, image_path: str, page_num: int
    ) -> dict[str, str]:
        """Process a single PDF page using the vision model."""

        try:
            # Read and encode image
            async with aiofiles.open(image_path, "rb") as image_file:
                image_data = await image_file.read()
                image_base64 = base64.b64encode(image_data).decode("utf-8")

            # Verify model supports vision
            if not self.supports_vision(model=self.config.vision_pdf_model):
                raise ValueError(
                    f"Model {self.config.vision_pdf_model} does not support vision"
                )

            # Configure generation parameters
            generation_config = GenerationConfig(
                model=self.config.vision_pdf_model,
                stream=False,
            )

            # Prepare message with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.vision_prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                }
            ]

            # Get completion from LiteLLM provider
            response = await self.llm_provider.aget_completion(
                messages=messages, generation_config=generation_config
            )

            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("No content in response")
                return {"page": str(page_num), "content": content}
            else:
                raise ValueError("No response content")

        except Exception as e:
            logger.error(
                f"Error processing page {page_num} with vision model: {str(e)}"
            )
            raise

    async def ingest(
        self, data: str | bytes, maintain_order: bool = False, **kwargs
    ) -> AsyncGenerator[dict[str, str], None]:
        """
        Ingest PDF data and yield descriptions for each page using vision model.

        Args:
            data: PDF file path or bytes
            maintain_order: If True, yields results in page order. If False, yields as completed.
            **kwargs: Additional arguments passed to the completion call

        Yields:
            Dict containing page number and content for each processed page
        """
        if not self.vision_prompt_text:
            self.vision_prompt_text = await self.database_provider.get_cached_prompt(  # type: ignore
                prompt_name=self.config.vision_pdf_prompt_name
            )

        temp_dir = None
        try:
            # Create temporary directory for image processing
            # temp_dir = os.path.join(os.getcwd(), "temp_pdf_images")
            # os.makedirs(temp_dir, exist_ok=True)
            temp_dir = self._create_temp_dir()

            # Handle both file path and bytes input
            if isinstance(data, bytes):
                pdf_path = os.path.join(temp_dir, "temp.pdf")
                async with aiofiles.open(pdf_path, "wb") as f:
                    await f.write(data)
            else:
                pdf_path = data

            # Convert PDF to images
            image_paths = await self.convert_pdf_to_images(pdf_path, temp_dir)
            # Create tasks for all pages
            tasks = {
                asyncio.create_task(
                    self.process_page(image_path, page_num)
                ): page_num
                for page_num, image_path in enumerate(image_paths, 1)
            }

            if maintain_order:
                # Store results in order
                pending = set(tasks.keys())
                results = {}
                next_page = 1

                while pending:
                    # Get next completed task
                    done, pending = await asyncio.wait(
                        pending, return_when=asyncio.FIRST_COMPLETED
                    )

                    # Process completed tasks
                    for task in done:
                        result = await task
                        page_num = int(result["page"])
                        results[page_num] = result

                        # Yield results in order
                        while next_page in results:
                            yield results.pop(next_page)["content"]
                            next_page += 1
            else:
                # Yield results as they complete
                for coro in asyncio.as_completed(tasks.keys()):
                    result = await coro
                    yield result["content"]

        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            raise

        finally:
            # Cleanup temporary files
            if temp_dir and os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, file))
                os.rmdir(temp_dir)


class BasicPDFParser(AsyncParser[str | bytes]):
    """A parser for PDF data."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        try:
            from pypdf import PdfReader

            self.PdfReader = PdfReader
        except ImportError:
            raise ValueError(
                "Error, `pypdf` is required to run `PyPDFParser`. Please install it using `pip install pypdf`."
            )

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest PDF data and yield text from each page."""
        if isinstance(data, str):
            raise ValueError("PDF data must be in bytes format.")
        pdf = self.PdfReader(BytesIO(data))
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text is not None:
                page_text = "".join(
                    filter(
                        lambda x: (
                            unicodedata.category(x)
                            in [
                                "Ll",
                                "Lu",
                                "Lt",
                                "Lm",
                                "Lo",
                                "Nl",
                                "No",
                            ]  # Keep letters and numbers
                            or "\u4E00" <= x <= "\u9FFF"  # Chinese characters
                            or "\u0600" <= x <= "\u06FF"  # Arabic characters
                            or "\u0400" <= x <= "\u04FF"  # Cyrillic letters
                            or "\u0370" <= x <= "\u03FF"  # Greek letters
                            or "\u0E00" <= x <= "\u0E7F"  # Thai
                            or "\u3040" <= x <= "\u309F"  # Japanese Hiragana
                            or "\u30A0" <= x <= "\u30FF"  # Katakana
                            or x in string.printable
                        ),
                        page_text,
                    )
                )  # Keep characters in common languages ; # Filter out non-printable characters
                yield page_text


class PDFParserUnstructured(AsyncParser[str | bytes]):
    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        try:
            from unstructured.partition.pdf import partition_pdf

            self.partition_pdf = partition_pdf

        except ImportError as e:
            logger.error("PDFParserUnstructured ImportError :  ", e)
            logger.error(
                """Please install missing modules using :
            pip install unstructured  unstructured_pytesseract  unstructured_inference
            pip install pdfplumber   matplotlib   pillow_heif  toml
            """
            )

    async def ingest(
        self,
        data: str | bytes,
        partition_strategy: str = "hi_res",
        chunking_strategy="by_title",
    ) -> AsyncGenerator[str, None]:
        # partition the pdf
        elements = self.partition_pdf(
            file=BytesIO(data),
            partition_strategy=partition_strategy,
            chunking_strategy=chunking_strategy,
        )
        for element in elements:
            yield element.text
