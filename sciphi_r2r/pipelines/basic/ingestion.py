"""
A simple example to demonstrate the usage of `BasicIngestionPipeline`.
"""
import logging
from typing import Any, Optional

from sciphi_r2r.core import IngestionPipeline, LoggingDatabaseConnection

logger = logging.getLogger(__name__)


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

    def process_data(self, data: str, data_type: str) -> str:
        """
        Process data into plaintext based on the data type.
        """
        if data_type == "txt":
            return data
        elif data_type == "json":
            return self._parse_json(data)
        elif data_type == "html":
            return self._parse_html(data)
        else:
            raise ValueError(f"Data type {data_type} not supported.")

    def parse_file(self, file_data: Any, file_type: str) -> str:
        """
        Parse file data into plaintext based on the file type.
        """
        raise NotImplementedError("Parsing file data is not implemented.")

    def parse_entry(self, entry_data: Any, entry_type: str) -> str:
        """
        Parse entry data into plaintext based on the entry type.
        """
        return self.process_data(entry_data, entry_type)

    def _parse_json(self, data: str) -> str:
        """
        Parse JSON data into plaintext.
        """
        raise NotImplementedError("Parsing JSON data is not implemented.")

    def _parse_html(self, data: str) -> str:
        """
        Parse HTML data into plaintext.
        """
        raise NotImplementedError("Parsing HTML data is not implemented.")
