from abc import abstractmethod
from typing import Any, Iterator, Optional

from ..abstractions.document import BasicDocument
from ..adapters import Adapter
from ..providers.logging import LoggingDatabaseConnection
from ..utils import generate_run_id
from .pipeline import Pipeline


class IngestionPipeline(Pipeline):
    def __init__(
        self,
        adapters: Optional[dict[Any, Adapter]] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipeline(self, *args, **kwargs) -> None:
        self.pipeline_run_info = {
            "run_id": generate_run_id(),
            "type": "ingestion",
        }

    @property
    @abstractmethod
    def supported_types(self) -> list[str]:
        """
        Returns a list of supported data types.
        """
        pass

    @abstractmethod
    def process_data(
        self, entry_type: str, entry_data: Any
    ) -> Iterator[BasicDocument]:
        """
        Process data into plaintext based on the data type and yield BasicDocument objects.
        """
        pass

    @abstractmethod
    def parse_entry(
        self, entry_type: str, entry_data: Any
    ) -> Iterator[BasicDocument]:
        """
        Parse entry data into plaintext based on the entry type and yield BasicDocument objects.
        """
        pass

    def run(
        self,
        document_id: str,
        blobs: dict[str, Any],
        metadata: Optional[dict] = None,
        **kwargs,
    ) -> Iterator[BasicDocument]:
        """
        Run the appropriate parsing method based on the data type and whether the data is a file or an entry.
        Yields the processed BasicDocument objects.
        """
        self.initialize_pipeline()

        if len(blobs) == 0:
            raise ValueError("No blobs provided to process.")

        for entry_type, blob in blobs.items():
            if entry_type not in self.supported_types:
                raise ValueError(f"IngestionType {entry_type} not supported.")
            yield from self.parse_entry(entry_type, blob)
