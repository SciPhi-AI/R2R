# type: ignore
import asyncio
import logging
import os
import string
import unicodedata
from io import BytesIO
from typing import AsyncGenerator

from core.base.abstractions import DataType
from core.base.parsers.base_parser import AsyncParser

logger = logging.getLogger()
ZEROX_DEFAULT_MODEL = "openai/gpt-4o-mini"


class PDFParser(AsyncParser[DataType]):
    """A parser for PDF data."""

    def __init__(self):
        try:
            from pypdf import PdfReader

            self.PdfReader = PdfReader
        except ImportError:
            raise ValueError(
                "Error, `pypdf` is required to run `PyPDFParser`. Please install it using `pip install pypdf`."
            )

    async def ingest(
        self, data: DataType, **kwargs
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


class PDFParserSix(AsyncParser[DataType]):
    """A parser for PDF data."""

    def __init__(self):
        try:
            from pdfminer.high_level import extract_text_to_fp
            from pdfminer.layout import LAParams

            self.extract_text_to_fp = extract_text_to_fp
            self.LAParams = LAParams
        except ImportError:
            raise ValueError(
                "Error, `pdfminer.six` is required to run `PDFParser`. Please install it using `pip install pdfminer.six`."
            )

    async def ingest(self, data: bytes, **kwargs) -> AsyncGenerator[str, None]:
        """Ingest PDF data and yield text from each page."""
        if not isinstance(data, bytes):
            raise ValueError("PDF data must be in bytes format.")

        pdf_file = BytesIO(data)

        async def process_page(page_number):
            output = BytesIO()
            await asyncio.to_thread(
                self.extract_text_to_fp,
                pdf_file,
                output,
                page_numbers=[page_number],
                laparams=self.LAParams(),
            )
            page_text = output.getvalue().decode("utf-8")
            return "".join(filter(lambda x: x in string.printable, page_text))

        from pdfminer.pdfdocument import PDFDocument
        from pdfminer.pdfparser import PDFParser as pdfminer_PDFParser

        parser = pdfminer_PDFParser(pdf_file)
        document = PDFDocument(parser)

        for page_number in range(len(list(document.get_pages()))):
            page_text = await process_page(page_number)
            if page_text:
                yield page_text


class PDFParserUnstructured(AsyncParser[DataType]):
    def __init__(self):
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
        data: DataType,
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


class PDFParserMarker(AsyncParser[DataType]):
    model_refs = None

    def __init__(self):
        try:
            from marker.convert import convert_single_pdf
            from marker.models import load_all_models

            self.convert_single_pdf = convert_single_pdf
            if PDFParserMarker.model_refs is None:
                PDFParserMarker.model_refs = load_all_models()

        except ImportError as e:
            raise ValueError(
                f"Error, marker is not installed {e}, please install using `pip install marker-pdf` "
            )

    async def ingest(
        self, data: DataType, **kwargs
    ) -> AsyncGenerator[str, None]:
        if isinstance(data, str):
            raise ValueError("PDF data must be in bytes format.")

        text, _, _ = self.convert_single_pdf(
            BytesIO(data), PDFParserMarker.model_refs
        )
        yield text


class ZeroxPDFParser(AsyncParser[DataType]):
    """An advanced PDF parser using zerox."""

    def __init__(self):
        """
        Use the zerox library to parse PDF data.

        Args:
            cleanup (bool, optional): Whether to clean up temporary files after processing. Defaults to True.
            concurrency (int, optional): The number of concurrent processes to run. Defaults to 10.
            file_data (Optional[str], optional): The file data to process. Defaults to an empty string.
            maintain_format (bool, optional): Whether to maintain the format from the previous page. Defaults to False.
            model (str, optional): The model to use for generating completions. Defaults to "gpt-4o-mini". Refer to LiteLLM Providers for the correct model name, as it may differ depending on the provider.
            temp_dir (str, optional): The directory to store temporary files, defaults to some named folder in system's temp directory. If already exists, the contents will be deleted before zerox uses it.
            custom_system_prompt (str, optional): The system prompt to use for the model, this overrides the default system prompt of zerox.Generally it is not required unless you want some specific behaviour. When set, it will raise a friendly warning. Defaults to None.
            kwargs (dict, optional): Additional keyword arguments to pass to the litellm.completion method. Refer to the LiteLLM Documentation and Completion Input for details.

        """
        try:
            # from pyzerox import zerox
            from .pyzerox import zerox

            self.zerox = zerox

        except ImportError as e:
            raise ValueError(
                f"Error, zerox installation failed with Error='{e}', please install through the R2R ingestion bundle with `pip install r2r -E ingestion-bundle` "
            )

    async def ingest(
        self, data: DataType, **kwargs
    ) -> AsyncGenerator[str, None]:
        if isinstance(data, str):
            raise ValueError("PDF data must be in bytes format.")

        model = kwargs.get("zerox_parsing_model", ZEROX_DEFAULT_MODEL)
        model = model.split("/")[-1]  # remove the provider prefix
        result = await self.zerox(
            file_data=data,
            model=model,
            verbose=True,
        )

        for page in result.pages:
            yield page.content
