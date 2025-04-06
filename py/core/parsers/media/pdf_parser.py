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

import pymupdf
from pypdf import PdfReader

from core.base.abstractions import GenerationConfig
from core.base.parsers.base_parser import AsyncParser
from core.base.providers import (
    CompletionProvider,
    DatabaseProvider,
    IngestionConfig,
)

logger = logging.getLogger()


class VLMPDFParser(AsyncParser[str | bytes]):
    """A parser for PDF documents using vision models for page processing with PyMuPDF."""

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

    async def process_page(
        self, image_data: bytes, page_num: int
    ) -> dict[str, str]:
        """Process a single PDF page using the vision model."""
        page_start = time.perf_counter()
        try:
            # Convert image bytes to base64
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            model = self.config.app.vlm

            # Configure generation parameters
            generation_config = GenerationConfig(
                model=self.config.app.vlm,
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
            req_start = time.perf_counter()

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

    async def ingest(
        self, data: str | bytes, maintain_order: bool = True, **kwargs
    ) -> AsyncGenerator[dict[str, str | int], None]:
        """Process PDF with PyMuPDF for better performance."""
        ingest_start = time.perf_counter()
        logger.info("Starting PDF ingestion using VLMPDFParser with PyMuPDF.")

        if not self.vision_prompt_text:
            self.vision_prompt_text = (
                await self.database_provider.prompts_handler.get_cached_prompt(
                    prompt_name=self.config.vision_pdf_prompt_name
                )
            )
            logger.info("Retrieved vision prompt text from database.")

        try:
            # Use a batch approach for better performance
            batch_size = 20

            # Open PDF document with PyMuPDF
            if isinstance(data, str):
                doc = pymupdf.open(data)
            else:
                doc = pymupdf.open(stream=data, filetype="pdf")

            max_pages = len(doc)
            logger.info(f"PDF has {max_pages} pages to process")

            # Process in batches
            for batch_start in range(0, max_pages, batch_size):
                batch_end = min(batch_start + batch_size, max_pages)
                logger.info(
                    f"Processing batch: pages {batch_start + 1}-{batch_end}/{max_pages}"
                )

                # Create tasks for this batch
                batch_tasks = []
                for page_idx in range(batch_start, batch_end):
                    page_num = page_idx + 1  # 1-indexed page numbers

                    # Get page pixmap (render the page)
                    page = doc[page_idx]
                    pix = page.get_pixmap(dpi=150)

                    # Convert to JPEG bytes directly
                    img_data = pix.tobytes("jpeg")

                    # Create task for processing this page
                    batch_tasks.append(self.process_page(img_data, page_num))

                # Process the batch concurrently
                batch_results = await asyncio.gather(*batch_tasks)

                # Yield results
                for page_idx, result in enumerate(batch_results):
                    page_num = batch_start + page_idx + 1
                    yield {
                        "content": result.get("content", "") or "",
                        "page_number": page_num,
                    }

                # Force garbage collection after each batch
                import gc

                gc.collect()

            # Close the document
            doc.close()

            total_elapsed = time.perf_counter() - ingest_start
            logger.info(
                f"Completed PDF ingestion in {total_elapsed:.2f} seconds"
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
