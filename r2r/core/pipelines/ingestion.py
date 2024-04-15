from abc import abstractmethod
from typing import Any, Iterator, Optional

from ..abstractions.document import DocumentPage
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
    ) -> Iterator[DocumentPage]:
        """
        Process data into plaintext based on the data type and yield DocumentPage objects.
        """
        pass

    @abstractmethod
    def parse_entry(
        self, entry_type: str, entry_data: Any
    ) -> Iterator[DocumentPage]:
        """
        Parse entry data into plaintext based on the entry type and yield DocumentPage objects.
        """
        pass

    def run(
        self,
        document_id: str,
        blobs: dict[str, Any],
        metadata: Optional[dict] = None,
        **kwargs,
    ) -> Iterator[DocumentPage]:
        """
        Run the appropriate parsing method based on the data type and whether the data is a file or an entry.
        Yields the processed DocumentPage objects.
        """
        pass
