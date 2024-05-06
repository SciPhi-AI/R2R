from abc import abstractmethod
from typing import AsyncGenerator, Iterator, Optional

from ..abstractions.document import Document, DocumentType, Extraction
from ..abstractions.pipes import AsyncPipe, PipeType
from ..parsers import Parser
from ..utils.logging import LoggingDatabaseConnection
from .loggable import LoggableAsyncPipe


class DocumentParsingPipe(LoggableAsyncPipe):
    INPUT_TYPE = AsyncGenerator[Document, None]
    OUTPUT_TYPE = AsyncGenerator[Extraction, None]

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

    @property
    def pipe_type(self) -> PipeType:
        return PipeType.PARSING

    @property
    def supported_types(self) -> list[str]:
        """
        Lists the data types supported by the pipe.
        """
        return [entry_type for entry_type in DocumentType]

    @abstractmethod
    async def parse(
        self, document: Document, *args, **kwargs
    ) -> Iterator[Extraction]:
        """
        Parse the document based on the type and yield `Extraction` objects.
        """
        pass
