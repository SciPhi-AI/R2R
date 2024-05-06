"""
Abstract base class for embedding pipe.
"""

import logging
from abc import abstractmethod
from typing import AsyncGenerator, Generator, Optional

from ..abstractions.document import Extraction, Fragment
from ..providers.embedding import EmbeddingProvider
from ..providers.vector_db import VectorDBProvider, VectorEntry
from ..utils import generate_run_id
from ..utils.logging import LoggingDatabaseConnection
from .async_pipe import AsyncPipe

logger = logging.getLogger(__name__)


class StoragePipe(AsyncPipe):
    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        self.vector_db_provider = vector_db_provider
        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipe(self, *args, **kwargs) -> None:
        self.pipe_run_info = {
            "run_id": generate_run_id(),
            "type": "storage",
        }

    @abstractmethod
    async def store(self, vector_entries: list[VectorEntry]) -> None:
        pass

    @abstractmethod
    async def run(
        self, vector_entries: AsyncGenerator[VectorEntry, None], **kwargs
    ) -> None:
        pass
