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
    def get_supported_types(self) -> list[str]:
        """
        Returns a list of supported data types.
        """
        pass

    @abstractmethod
    def process_data(self, entry_type: str, entry_data: Any) -> str:
        """
        Process data into plaintext based on the data type.
        """
        pass

    @abstractmethod
    def parse_entry(self, entry_type: str, entry_data: Any) -> str:
        """
        Parse entry data into plaintext based on the entry type.
        """
        pass

    @abstractmethod
    def run(
        self,
        document_id: str,
        blobs: dict[str, Any],
        metadata: Optional[dict] = None,
        **kwargs
    ) -> BasicDocument:
        """
        Run the appropriate parsing method based on the data type and whether the data is a file or an entry.
        Returns the processed data and metadata.
        """
        pass
