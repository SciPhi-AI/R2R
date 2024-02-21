"""
A simple example to demonstrate the usage of `BasicIngestionPipeline`.
"""
import collections
import copy
import json
import logging
from enum import Enum
from typing import Optional, Union

from r2r.core import (
    BasicDocument,
    IngestionPipeline,
    LoggingDatabaseConnection,
)

logger = logging.getLogger(__name__)


class EntryType(Enum):
    TXT = "txt"
    JSON = "json"
    HTML = "html"
    PDF = "pdf"


class BasicIngestionPipeline(IngestionPipeline):
    def __init__(
        self,
        logging_database: Optional[LoggingDatabaseConnection] = None,
    ):
        logger.info(
            f"Initalizing a `BasicIngestionPipeline` to process incoming documents."
        )

        super().__init__(
            logging_database,
        )

    def get_supported_types(self) -> list[str]:
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

    def run(
        self,
        document_id: str,
        blobs: dict[str, Union[bytes, str]],
        metadata: Optional[dict] = None,
        **kwargs,
    ) -> dict:
        """
        Run the appropriate parsing method based on the data type and whether the data is a file or an entry.
        Returns the processed data and metadata.
        """
        if len(blobs) == 0:
            raise ValueError("No blobs provided to process.")

        processed_text = ""
        for entry_type, blob in blobs.items():
            if entry_type not in self.get_supported_types():
                raise ValueError(f"EntryType {entry_type} not supported.")
            processed_text += self.parse_entry(entry_type, blob)

        return BasicDocument(
            id=document_id, text=processed_text, metadata=metadata
        )

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
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(data, "html.parser")
        return soup.get_text()

    def _parse_pdf(self, file_data: bytes) -> str:
        import string
        from io import BytesIO

        from pypdf import PdfReader

        """
        Process PDF file data into plaintext.
        """
        pdf = PdfReader(BytesIO(file_data))
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
