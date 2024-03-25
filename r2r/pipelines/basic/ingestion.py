"""
A simple example to demonstrate the usage of `BasicIngestionPipeline`.
"""
import logging
from enum import Enum
from typing import Any, Iterator, Optional, Union

from r2r.core import (
    BasicDocument,
    IngestionPipeline,
    LoggingDatabaseConnection,
)
from r2r.core.adapters import (
    Adapter,
    HTMLAdapter,
    JSONAdapter,
    PDFAdapter,
    TextAdapter,
)

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
        adapters: Optional[dict[EntryType, Adapter]] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
    ):
        logger.info(
            f"Initializing a `BasicIngestionPipeline` to process incoming documents."
        )

        super().__init__(
            logging_connection,
        )
        self.pipeline_run_info = None
        self.default_adapters = {
            EntryType.TXT: TextAdapter(),
            EntryType.JSON: JSONAdapter(),
            EntryType.HTML: HTMLAdapter(),
            EntryType.PDF: PDFAdapter(),
        }
        self.adapters = self.default_adapters
        if adapters is not None:
            for entry_type, adapter in adapters.items():
                self.adapters[entry_type] = adapter

    @property
    def supported_types(self) -> list[str]:
        """
        Lists the data types supported by the pipeline.
        """
        return [entry_type.value for entry_type in EntryType]

    def process_data(
        self,
        entry_type: EntryType,
        entry_data: Union[bytes, str],
    ) -> Iterator[BasicDocument]:
        adapter = self.adapters.get(
            entry_type, self.default_adapters[entry_type]
        )
        text = adapter.adapt(entry_data)
        yield BasicDocument(
            id=self.document_id, text=text, metadata=self.metadata
        )

    def parse_entry(
        self, entry_type: str, entry_data: Union[bytes, str]
    ) -> Iterator[BasicDocument]:
        yield from self.process_data(EntryType(entry_type), entry_data)

    def run(
        self,
        document_id: str,
        blobs: dict[str, Any],
        metadata: Optional[dict] = None,
        **kwargs,
    ) -> Iterator[BasicDocument]:
        self.initialize_pipeline()
        self.document_id = document_id
        self.metadata = metadata or {}

        if len(blobs) == 0:
            raise ValueError("No blobs provided to process.")

        for entry_type, blob in blobs.items():
            if entry_type not in self.supported_types:
                raise ValueError(f"EntryType {entry_type} not supported.")
            yield from self.parse_entry(entry_type, blob)
