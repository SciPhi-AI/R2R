# type: ignore

# Standard library imports
import asyncio
import base64
import logging
import os
import string
import tempfile
import time
import unicodedata
import uuid
from io import BytesIO
from typing import AsyncGenerator

# Third-party imports
import aiofiles
from pdf2image import convert_from_bytes, convert_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError
from PIL import Image

# Local application imports
from core.base.abstractions import GenerationConfig
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)
from shared.abstractions import PDFParsingError, PopperNotFoundError

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
                "Please install the litellm package to use the VLMPDFParser."
            )
        # Check once if the model supports vision
        if not self.supports_vision(model=self.config.vision_pdf_model):
            msg = (
                f"Model {self.config.vision_pdf_model} does not support vision"
            )
            logger.error(msg)
            raise ValueError(msg)
        logger.info(
            f"Initialized VLMPDFParser with model {self.config.vision_pdf_model}"
        )

    async def convert_pdf_to_images(
        self, data: str | bytes
    ) -> list[Image.Image]:
        """
        Convert PDF pages to images asynchronously using in-memory conversion.
        """
        logger.info("Starting PDF conversion to images.")
        start_time = time.perf_counter()
        options = {
            "dpi": 300,  # You can make this configurable via self.config if needed
            "fmt": "jpeg",
            "thread_count": 4,
            "paths_only": False,  # Return PIL Image objects instead of writing to disk
        }
        try:
            if isinstance(data, bytes):
                images = await asyncio.to_thread(
                    convert_from_bytes, data, **options
                )
            else:
                images = await asyncio.to_thread(
                    convert_from_path, data, **options
                )
            elapsed = time.perf_counter() - start_time
            logger.info(
                f"PDF conversion completed in {elapsed:.2f} seconds, total pages: {len(images)}"
            )
            return images
        except PDFInfoNotInstalledError:
            logger.error(
                "PDFInfoNotInstalledError encountered during PDF conversion."
            )
            raise PopperNotFoundError()
        except Exception as err:
            logger.error(
                f"Error converting PDF to images: {err} type: {type(err)}"
            )
            raise PDFParsingError(f"Failed to process PDF: {str(err)}", err)

    async def process_page(
        self, image: Image.Image, page_num: int
    ) -> dict[str, str]:
        """Process a single PDF page using the vision model."""
        page_start = time.perf_counter()
        try:
            # Convert PIL image to JPEG bytes in-memory
            buf = BytesIO()
            image.save(buf, format="JPEG")
            buf.seek(0)
            image_data = buf.read()
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            # Configure generation parameters
            generation_config = GenerationConfig(
                model=self.config.vision_pdf_model,
                stream=False,
            )

            # Prepare message with image content
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

            logger.debug(f"Sending page {page_num} to vision model.")
            req_start = time.perf_counter()
            response = await self.llm_provider.aget_completion(
                messages=messages, generation_config=generation_config
            )
            req_elapsed = time.perf_counter() - req_start
            logger.debug(
                f"Vision model response for page {page_num} received in {req_elapsed:.2f} seconds."
            )

            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                page_elapsed = time.perf_counter() - page_start
                logger.info(
                    f"Processed page {page_num} in {page_elapsed:.2f} seconds."
                )
                return {"page": str(page_num), "content": content}
            else:
                msg = f"No response content for page {page_num}"
                logger.error(msg)
                raise ValueError(msg)
        except Exception as e:
            logger.error(
                f"Error processing page {page_num} with vision model: {str(e)}"
            )
            raise

    async def ingest(
        self, data: str | bytes, maintain_order: bool = True, **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Ingest PDF data and yield the text description for each page using the vision model.
        (This version yields a string per page rather than a dictionary.)
        """
        ingest_start = time.perf_counter()
        logger.info("Starting PDF ingestion using VLMPDFParser.")
        if not self.vision_prompt_text:
            self.vision_prompt_text = (
                await self.database_provider.prompts_handler.get_cached_prompt(
                    prompt_name=self.config.vision_pdf_prompt_name
                )
            )
            logger.info("Retrieved vision prompt text from database.")

        try:
            # Convert PDF to images (in-memory)
            images = await self.convert_pdf_to_images(data)

            # Create asynchronous tasks for processing each page
            tasks = {
                asyncio.create_task(
                    self.process_page(image, page_num)
                ): page_num
                for page_num, image in enumerate(images, 1)
            }

            if maintain_order:
                pending = set(tasks.keys())
                results = {}
                next_page = 1
                while pending:
                    done, pending = await asyncio.wait(
                        pending, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in done:
                        result = await task
                        page_num = int(result["page"])
                        results[page_num] = result
                        # **Fix:** Yield only the content string instead of the whole dictionary.
                        while next_page in results:
                            yield results.pop(next_page)["content"]
                            next_page += 1
            else:
                # Yield results as tasks complete
                for coro in asyncio.as_completed(tasks.keys()):
                    result = await coro
                    # **Fix:** Yield only the content string.
                    yield result["content"]
            total_elapsed = time.perf_counter() - ingest_start
            logger.info(
                f"Completed PDF ingestion in {total_elapsed:.2f} seconds using VLMPDFParser."
            )
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            raise


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
