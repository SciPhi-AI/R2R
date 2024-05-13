"""
Abstract base class for embedding pipe.
"""

import logging
from abc import abstractmethod
from typing import AsyncGenerator, Optional

from ...core.abstractions.rag import RAGRequest, RAGResult
from ...core.pipes.base import AsyncPipe, PipeType
from ...core.pipes.logging import PipeLoggingConnectionSingleton
from ...core.providers.vector_db import VectorDBProvider

logger = logging.getLogger(__name__)


class RAGPipe(AsyncPipe):
    INPUT_TYPE = RAGRequest
    OUTPUT_TYPE = AsyncGenerator[RAGResult, None]

    def __init__(
        self,
        vector_db_provider: VectorDBProvider,
        pipe_logger: Optional[PipeLoggingConnectionSingleton] = None,
        *args,
        **kwargs,
    ):
        self.vector_db_provider = vector_db_provider
        super().__init__(pipe_logger=pipe_logger, *args, **kwargs)

    @property
    def type(self) -> PipeType:
        return PipeType.RAG

    @abstractmethod
    async def rag(
        self, request: RAGRequest
    ) -> AsyncGenerator[RAGResult, None]:
        pass

    @abstractmethod
    async def run(self, input: INPUT_TYPE, **kwargs) -> OUTPUT_TYPE:
        pass
