"""
Abstract base class for embedding pipe.
"""

import logging
from abc import abstractmethod
from typing import AsyncGenerator, Optional

from ..abstractions.document import Extraction, Fragment
from ..abstractions.pipes import PipeType
from ..providers.embedding import EmbeddingProvider
from ..providers.vector_db import VectorEntry
from ..utils.logging import LoggingDatabaseConnection
from .loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class EmbeddingPipe(LoggableAsyncPipe):
    INPUT_TYPE = AsyncGenerator[Extraction, None]
    OUTPUT_TYPE = AsyncGenerator[VectorEntry, None]

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.embedding_provider = embedding_provider
        super().__init__(logging_connection=logging_connection, **kwargs)

    @property
    def type(self) -> PipeType:
        return PipeType.EMBEDDING

    @abstractmethod
    async def fragment(
        self, extraction: Extraction
    ) -> AsyncGenerator[Fragment, None]:
        pass

    @abstractmethod
    async def transform_fragments(
        self, fragments: list[Fragment], metadatas: list[dict]
    ) -> AsyncGenerator[Fragment, None]:
        pass

    @abstractmethod
    async def embed(self, fragments: list[Fragment]) -> list[list[float]]:
        pass

    @abstractmethod
    async def run(self, input: INPUT_TYPE, **kwargs) -> OUTPUT_TYPE:
        pass
