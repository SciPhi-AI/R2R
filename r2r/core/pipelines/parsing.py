from abc import abstractmethod
from typing import Iterator, Optional

from ..abstractions.document import Document, DocumentType, Extraction
from ..parsers import Parser
from ..utils import generate_run_id
from ..utils.logging import LoggingDatabaseConnection
from .async_pipeline import AsyncPipeline


class DocumentParsingPipeline(AsyncPipeline):
    def __init__(
        self,
        selected_parsers: Optional[dict[DocumentType, Parser]] = None,
        override_parsers: Optional[dict[DocumentType, Parser]] = None,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.selected_parsers = selected_parsers or {}
        self.override_parsers = override_parsers or {}
        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipeline(self, *args, **kwargs) -> None:
        self.pipeline_run_info = {
            "run_id": generate_run_id(),
            "type": "parsing",
        }

    @property
    @abstractmethod
    def supported_types(self) -> list[str]:
        """
        Returns a list of supported data types.
        """
        pass

    @abstractmethod
    async def parse(
        self, document: Document, *args, **kwargs
    ) -> Iterator[Extraction]:
        """
        Parse the document based on the type and yield `Extraction` objects.
        """
        pass

    async def run(
        self,
        documents: list[Document],
        *args,
        **kwargs,
    ) -> Iterator[Extraction]:
        """
        Parses the provided documents.
        """
        pass
