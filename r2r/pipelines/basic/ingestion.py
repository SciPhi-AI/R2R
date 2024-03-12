"""
A simple example to demonstrate the usage of `BasicIngestionPipeline`.
"""
import collections
import copy
import json
import logging
from enum import Enum
from typing import Optional, Union

from r2r.core import IngestionPipeline, LoggingDatabaseConnection

logger = logging.getLogger(__name__)


class EntryType(Enum):
    TXT = "txt"
    JSON = "json"
    HTML = "html"
    PDF = "pdf"


class BasicIngestionPipeline(IngestionPipeline):
    """
    Processes incoming documents into plaintext based on their data type.
    Supports TXT, JSON, HTML, and PDF formats.
    """

    def __init__(
        self,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
    ):
        try:
            from bs4 import BeautifulSoup

            self.BeautifulSoup = BeautifulSoup
        except ImportError:
            raise ValueError(
                "Error, `bs4` is requried to run `BasicIngestionPipeline`. Please install it using `pip install bs4`."
            )

        try:
            from pypdf import PdfReader

            self.PdfReader = PdfReader
        except ImportError:
            raise ValueError(
                "Error, `pypdf` is requried to run `BasicIngestionPipeline`. Please install it using `pip install pypdf`."
            )

        logger.info(
            f"Initalizing a `BasicIngestionPipeline` to process incoming documents."
        )

        super().__init__(
            logging_connection,
        )
        self.pipeline_run_info = None

    @property
    def supported_types(self) -> list[str]:
        """
        Lists the data types supported by the pipeline.
        """
        return [entry_type.value for entry_type in EntryType]

    def process_data(
        self,
        entry_type: str,
        entry_data: Union[bytes, str],
    ) -> str:
        """
        Process data into plaintext based on the data type.
        """
        if entry_type == EntryType.TXT.value:
            if not isinstance(entry_data, str):
                raise ValueError("TXT data must be a string.")
            return entry_data
        elif entry_type == EntryType.JSON.value:
            try:
                entry_json = json.loads(entry_data)
            except json.JSONDecodeError:
                raise ValueError("JSON data must be a valid JSON string.")
            return self._parse_json(entry_json)
        elif entry_type == EntryType.HTML.value:
            if not isinstance(entry_data, str):
                raise ValueError("HTML data must be a string.")
            return self._parse_html(entry_data)
        elif entry_type == EntryType.PDF.value:
            if not isinstance(entry_data, bytes):
                raise ValueError("PDF data must be a bytes object.")
            return self._parse_pdf(entry_data)
        else:
            raise ValueError(f"EntryType {entry_type} not supported.")

    def parse_entry(
        self, entry_type: str, entry_data: Union[bytes, str]
    ) -> str:
        """
        Parse entry data into plaintext based on the entry type.
        """
        return self.process_data(entry_type, entry_data)

    def _parse_json(self, data: dict) -> str:
        """
        Parse JSON data into plaintext.
        """

        def remove_objects_with_null(obj):
            if not isinstance(obj, collections.abc.Mapping):
                return obj
            result = copy.deepcopy(obj)
            for key, value in obj.items():
                if isinstance(value, collections.abc.Mapping):
                    result[key] = remove_objects_with_null(value)
                elif value is None:
                    del result[key]
            return result

        def format_json_as_text(obj, indent=0):
            """
            Recursively formats a JSON object as a text document, placing nested components on new lines with indentation.

            Args:
                obj: The JSON object to format.
                indent: The current indentation level.

            Returns:
                A string representing the formatted text document.
            """
            lines = []
            indent_str = "" * indent  # Two spaces per indentation level

            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, (dict, list)):
                        nested = format_json_as_text(value, indent + 1)
                        lines.append(f"{indent_str}{key}:\n{nested}")
                    else:
                        lines.append(f"{indent_str}{key}: {value}")
            elif isinstance(obj, list):
                for item in obj:
                    nested = format_json_as_text(item, indent + 1)
                    lines.append(f"{nested}")
            else:
                return f"{indent_str}{obj}"

            return "\n".join(lines)

        return format_json_as_text(remove_objects_with_null(data))

    def _parse_html(self, data: str) -> str:
        """
        Parse HTML data into plaintext.
        """

        soup = self.BeautifulSoup(data, "html.parser")
        return soup.get_text()

    def _parse_pdf(self, file_data: bytes) -> str:
        import string
        from io import BytesIO

        """
        Process PDF file data into plaintext.
        """
        pdf = self.PdfReader(BytesIO(file_data))
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text is not None:
                # Remove non-printable characters
                page_text = "".join(
                    filter(lambda x: x in string.printable, page_text)
                )
                text += page_text + "\n"
        return text
