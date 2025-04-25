# type: ignore
import asyncio
import base64
import json
import logging
import string
import time
import unicodedata
from io import BytesIO
from typing import AsyncGenerator

import pdf2image
from mistralai.models import OCRResponse
from pypdf import PdfReader

from core.base.abstractions import GenerationConfig
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
    OCRProvider,
)

logger = logging.getLogger()


class OCRPDFParser(AsyncParser[str | bytes]):
    """
    A parser for PDF documents using Mistral's OCR for page processing.

    Mistral supports directly processing PDF files, so this parser is a simple wrapper around the Mistral OCR API.
    """

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
        ocr_provider: OCRProvider,
    ):
        self.config = config
        self.database_provider = database_provider
        self.ocr_provider = ocr_provider

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ingest PDF data and yield text from each page."""
        try:
            logger.info("Starting PDF ingestion using MistralOCRParser")

            if isinstance(data, str):
                response: OCRResponse = await self.ocr_provider.process_pdf(
                    file_path=data
                )
            else:
                response: OCRResponse = await self.ocr_provider.process_pdf(
                    file_content=data
                )

            for page in response.pages:
                yield {
                    "content": page.markdown,
                    "page_number": page.index + 1,  # Mistral is 0-indexed
                }

        except Exception as e:
            logger.error(f"Error processing PDF with Mistral OCR: {str(e)}")
            raise


class VLMPDFParser(AsyncParser[str | bytes]):
    """A parser for PDF documents using vision models for page processing."""

    def __init__(
        self,
        config: IngestionConfig,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
        ocr_provider: OCRProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        self.vision_prompt_text = None
        self.vlm_batch_size = self.config.vlm_batch_size or 5
        self.max_concurrent_vlm_tasks = (
            self.config.max_concurrent_vlm_tasks or 5
        )
        self.semaphore = None

    async def process_page(self, image, page_num: int) -> dict[str, str]:
        """Process a single PDF page using the vision model."""
        page_start = time.perf_counter()
        try:
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format="JPEG")
            image_data = img_byte_arr.getvalue()
            # Convert image bytes to base64
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            model = self.config.app.vlm

            # Configure generation parameters
            generation_config = GenerationConfig(
                model=self.config.vlm or self.config.app.vlm,
                stream=False,
            )

            is_anthropic = model and "anthropic/" in model

            # Prepare message with image content
            if is_anthropic:
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.vision_prompt_text},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64,
                                },
                            },
                        ],
                    }
                ]
            else:
                # Use OpenAI format
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

            if is_anthropic:
                response = await self.llm_provider.aget_completion(
                    messages=messages,
                    generation_config=generation_config,
                    tools=[
                        {
                            "name": "parse_pdf_page",
                            "description": "Parse text content from a PDF page",
                            "input_schema": {
                                "type": "object",
                                "properties": {
                                    "page_content": {
                                        "type": "string",
                                        "description": "Extracted text from the PDF page, transcribed into markdown",
                                    },
                                    "thoughts": {
                                        "type": "string",
                                        "description": "Any thoughts or comments on the text",
                                    },
                                },
                                "required": ["page_content"],
                            },
                        }
                    ],
                    tool_choice={"type": "tool", "name": "parse_pdf_page"},
                )

                if (
                    response.choices
                    and response.choices[0].message
                    and response.choices[0].message.tool_calls
                ):
                    tool_call = response.choices[0].message.tool_calls[0]
                    args = json.loads(tool_call.function.arguments)
                    content = args.get("page_content", "")
                    page_elapsed = time.perf_counter() - page_start
                    logger.debug(
                        f"Processed page {page_num} in {page_elapsed:.2f} seconds."
                    )
                    return {"page": str(page_num), "content": content}
                else:
                    logger.warning(
                        f"No valid tool call in response for page {page_num}, document might be missing text."
                    )
                    return {"page": str(page_num), "content": ""}
            else:
                response = await self.llm_provider.aget_completion(
                    messages=messages, generation_config=generation_config
                )

                if response.choices and response.choices[0].message:
                    content = response.choices[0].message.content
                    page_elapsed = time.perf_counter() - page_start
                    logger.debug(
                        f"Processed page {page_num} in {page_elapsed:.2f} seconds."
                    )
                    return {"page": str(page_num), "content": content}
                else:
                    msg = f"No response content for page {page_num}"
                    logger.error(msg)
                    return {"page": str(page_num), "content": ""}
        except Exception as e:
            logger.error(
                f"Error processing page {page_num} with vision model: {str(e)}"
            )
            # Return empty content rather than raising to avoid failing the entire batch
            return {
                "page": str(page_num),
                "content": f"Error processing page: {str(e)}",
            }
        finally:
            import gc

            gc.collect()

    async def process_and_yield(self, image, page_num: int):
        """Process a page and yield the result."""
        async with self.semaphore:
            result = await self.process_page(image, page_num)
            return {
                "content": result.get("content", "") or "",
                "page_number": page_num,
            }

    async def ingest(
        self, data: str | bytes, **kwargs
    ) -> AsyncGenerator[dict[str, str | int], None]:
        """Process PDF as images using pdf2image."""
        ingest_start = time.perf_counter()
        logger.info("Starting PDF ingestion using VLMPDFParser.")

        if not self.vision_prompt_text:
            self.vision_prompt_text = (
                await self.database_provider.prompts_handler.get_cached_prompt(
                    prompt_name="vision_pdf"
                )
            )
            logger.info("Retrieved vision prompt text from database.")

        self.semaphore = asyncio.Semaphore(self.max_concurrent_vlm_tasks)

        try:
            if isinstance(data, str):
                pdf_info = pdf2image.pdfinfo_from_path(data)
            else:
                pdf_bytes = BytesIO(data)
                pdf_info = pdf2image.pdfinfo_from_bytes(pdf_bytes.getvalue())

            max_pages = pdf_info["Pages"]
            logger.info(f"PDF has {max_pages} pages to process")

            # Create a task queue to process pages in order
            pending_tasks = []
            completed_tasks = []
            next_page_to_yield = 1

            # Process pages with a sliding window, in batches
            for batch_start in range(1, max_pages + 1, self.vlm_batch_size):
                batch_end = min(
                    batch_start + self.vlm_batch_size - 1, max_pages
                )
                logger.debug(
                    f"Preparing batch of pages {batch_start}-{batch_end}/{max_pages}"
                )

                # Convert the batch of pages to images
                if isinstance(data, str):
                    images = pdf2image.convert_from_path(
                        data,
                        dpi=150,
                        first_page=batch_start,
                        last_page=batch_end,
                    )
                else:
                    pdf_bytes = BytesIO(data)
                    images = pdf2image.convert_from_bytes(
                        pdf_bytes.getvalue(),
                        dpi=150,
                        first_page=batch_start,
                        last_page=batch_end,
                    )

                # Create tasks for each page in the batch
                for i, image in enumerate(images):
                    page_num = batch_start + i
                    task = asyncio.create_task(
                        self.process_and_yield(image, page_num)
                    )
                    task.page_num = page_num  # Store page number for sorting
                    pending_tasks.append(task)

                # Check if any tasks have completed and yield them in order
                while pending_tasks:
                    # Get the first done task without waiting
                    done_tasks, pending_tasks_set = await asyncio.wait(
                        pending_tasks,
                        timeout=0.01,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if not done_tasks:
                        break

                    # Add completed tasks to our completed list
                    pending_tasks = list(pending_tasks_set)
                    completed_tasks.extend(iter(done_tasks))

                    # Sort completed tasks by page number
                    completed_tasks.sort(key=lambda t: t.page_num)

                    # Yield results in order
                    while (
                        completed_tasks
                        and completed_tasks[0].page_num == next_page_to_yield
                    ):
                        task = completed_tasks.pop(0)
                        yield await task
                        next_page_to_yield += 1

            # Wait for and yield any remaining tasks in order
            while pending_tasks:
                done_tasks, _ = await asyncio.wait(pending_tasks)
                completed_tasks.extend(done_tasks)
                pending_tasks = []

                # Sort and yield remaining completed tasks
                completed_tasks.sort(key=lambda t: t.page_num)

                # Yield results in order
                while (
                    completed_tasks
                    and completed_tasks[0].page_num == next_page_to_yield
                ):
                    task = completed_tasks.pop(0)
                    yield await task
                    next_page_to_yield += 1

            total_elapsed = time.perf_counter() - ingest_start
            logger.info(
                f"Completed PDF conversion in {total_elapsed:.2f} seconds"
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
        self.PdfReader = PdfReader

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
                            or "\u4e00" <= x <= "\u9fff"  # Chinese characters
                            or "\u0600" <= x <= "\u06ff"  # Arabic characters
                            or "\u0400" <= x <= "\u04ff"  # Cyrillic letters
                            or "\u0370" <= x <= "\u03ff"  # Greek letters
                            or "\u0e00" <= x <= "\u0e7f"  # Thai
                            or "\u3040" <= x <= "\u309f"  # Japanese Hiragana
                            or "\u30a0" <= x <= "\u30ff"  # Katakana
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
        ocr_provider: OCRProvider,
    ):
        self.database_provider = database_provider
        self.llm_provider = llm_provider
        self.config = config
        try:
            from unstructured.partition.pdf import partition_pdf

            self.partition_pdf = partition_pdf

        except ImportError as e:
            logger.error("PDFParserUnstructured ImportError :  ", e)

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
