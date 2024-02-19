from abc import ABC, abstractmethod
from typing import Any, Optional

from ..abstractions.document import BasicDocument
from ..providers.logging import LoggingDatabaseConnection


class IngestionPipeline(ABC):
    def __init__(
        self,
        logging_database: Optional[LoggingDatabaseConnection] = None,
        **kwargs
    ):
        self.logging_database = logging_database

    @abstractmethod
    def process_data(self, data: Any, data_type: str) -> str:
        """
        Process data into plaintext based on the data type.
        """
        pass

    @abstractmethod
    def parse_file(self, file_data: Any, file_type: str) -> str:
        """
        Parse file data into plaintext based on the file type.
        """
        pass

    @abstractmethod
    def parse_entry(self, entry_data: Any, entry_type: str) -> str:
        """
        Parse entry data into plaintext based on the entry type.
        """
        pass

    def run(
        self,
        document_id: str,
        data: Any,
        data_type: str,
        is_file: bool = False,
        **kwargs
    ) -> dict:
        """
        Run the appropriate parsing method based on the data type and whether the data is a file or an entry.
        Returns the processed data and metadata.
        """
        processed_data = None
        metadata = kwargs.get("metadata", {})

        if is_file:
            processed_data = self.parse_file(data, data_type)
        else:
            processed_data = self.parse_entry(data, data_type)

        return BasicDocument(
            id=document_id, text=processed_data, metadata=metadata
        )
