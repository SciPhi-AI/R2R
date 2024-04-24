"""
A simple example to demonstrate the usage of `BasicIngestionPipeline`.
"""

import logging
from typing import Any, Iterator, Optional, Union

from r2r.core import (
    DocumentPage,
    IngestionPipeline,
    IngestionType,
    LoggingDatabaseConnection,
)
from r2r.core.ingestors import (
    CSVAdapter,
    DOCXAdapter,
    HTMLAdapter,
    Ingestor,
    JSONAdapter,
    MarkdownAdapter,
    PDFAdapter,
    PPTAdapter,
    TextAdapter,
    XLSXAdapter,
)

logger = logging.getLogger(__name__)


class BasicIngestionPipeline(IngestionPipeline):
    """
    Processes incoming documents into plaintext based on their data type.
    Supports TXT, JSON, HTML, and PDF formats.
    """

    AVAILABLE_ADAPTERS = {
        IngestionType.CSV: {"default": CSVAdapter},
        IngestionType.DOCX: {"default": DOCXAdapter},
        IngestionType.HTML: {"default": HTMLAdapter},
        IngestionType.JSON: {"default": JSONAdapter},
        IngestionType.MD: {"default": MarkdownAdapter},
        IngestionType.PDF: {"default": PDFAdapter},
        IngestionType.PPTX: {"default": PPTAdapter},
        IngestionType.TXT: {"default": TextAdapter},
        IngestionType.XLSX: {"default": XLSXAdapter},
    }

    def __init__(
        self,
        selected_ingestors: Optional[dict[IngestionType, str]] = None,
        override_ingestors: Optional[dict[IngestionType, Ingestor]] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
    ):
        logger.info(
            f"Initializing a `BasicIngestionPipeline` to process incoming documents."
        )

        super().__init__(
            logging_connection,
        )
        self.pipeline_run_info = None
        self.ingestors = {}
        if selected_ingestors is not None:
            for ingestion_type, Ingestor in selected_ingestors.items():
                if ingestion_type not in self.AVAILABLE_ADAPTERS:
                    raise ValueError(
                        f"Ingestor for {ingestion_type} not supported by `BasicIngestionPipeline`."
                    )
                if Ingestor not in self.AVAILABLE_ADAPTERS[ingestion_type]:
                    raise ValueError(
                        f"Ingestor `{Ingestor}` not available for `{ingestion_type}` in `BasicIngestionPipeline`."
                    )
                self.ingestors[ingestion_type] = self.AVAILABLE_ADAPTERS[
                    ingestion_type
                ][Ingestor]()

        if override_ingestors is not None:
            for entry_type, Ingestor in override_ingestors.items():
                self.ingestors[entry_type] = Ingestor

    @property
    def supported_types(self) -> list[str]:
        """
        Lists the data types supported by the pipeline.
        """
        return [entry_type.value for entry_type in IngestionType]

    def process_data(
        self,
        entry_type: IngestionType,
        entry_data: Union[bytes, str],
    ) -> Iterator[DocumentPage]:
        if entry_type not in self.ingestors:
            raise ValueError(
                f"Ingestor for {entry_type} not found in `BasicIngestionPipeline`."
            )
        Ingestor = self.ingestors[entry_type]
        texts = Ingestor.ingest(entry_data)
        for iteration, text in enumerate(texts):
            yield DocumentPage(
                document_id=self.document_id,
                page_number=iteration,
                text=text,
                metadata=self.metadata,
            )

    def parse_entry(
        self, entry_type: str, entry_data: Union[bytes, str]
    ) -> Iterator[DocumentPage]:
        yield from self.process_data(IngestionType(entry_type), entry_data)

    def run(
        self,
        document_id: str,
        blobs: dict[str, Any],
        metadata: Optional[dict] = None,
        **kwargs,
    ) -> Iterator[DocumentPage]:
        self.initialize_pipeline()
        self.document_id = document_id
        self.metadata = metadata or {}

        if len(blobs) == 0:
            raise ValueError("No blobs provided to process.")

        for entry_type, blob in blobs.items():
            if entry_type not in self.supported_types:
                raise ValueError(f"IngestionType {entry_type} not supported.")
            yield from self.parse_entry(entry_type, blob)
