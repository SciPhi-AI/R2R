import uuid
from abc import abstractmethod
from typing import Any, Optional

from ..abstractions.document import BasicDocument
from ..providers.logging import LoggingDatabaseConnection
from .pipeline import Pipeline


class IngestionPipeline(Pipeline):
    def __init__(
        self,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipeline(self, *args, **kwargs) -> None:
        self.pipeline_run_info = {"run_id": uuid.uuid4(), "type": "ingestion"}

    @property
    @abstractmethod
    def supported_types(self) -> list[str]:
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

    def run(
        self,
        document_id: str,
        blobs: dict[str, Any],
        metadata: Optional[dict] = None,
        **kwargs,
    ) -> BasicDocument:
        """
        Run the appropriate parsing method based on the data type and whether the data is a file or an entry.
        Returns the processed data and metadata.
        """

        self.initialize_pipeline()

        if len(blobs) == 0:
            raise ValueError("No blobs provided to process.")

        processed_text = ""
        for entry_type, blob in blobs.items():
            if entry_type not in self.supported_types:
                raise ValueError(f"EntryType {entry_type} not supported.")
            processed_text += self.parse_entry(entry_type, blob)

        return BasicDocument(
            id=document_id, text=processed_text, metadata=metadata or {}
        )
