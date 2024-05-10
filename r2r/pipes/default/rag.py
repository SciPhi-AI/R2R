import logging
from typing import Any, AsyncGenerator, Optional, Union

from pydantic import BaseModel

from r2r.core import (
    AsyncContext,
    AsyncPipe,
    EmbeddingProvider,
    PipeConfig,
    PipeFlow,
    PipeType,
    SearchResult,
    VectorDBProvider,
)

logger = logging.getLogger(__name__)


class DefaultRAGPipe(AsyncPipe):
    """
    Stores embeddings in a vector database asynchronously.
    """

    class RAGConfig(BaseModel, PipeConfig):
        name: str = "default_rag"

    class Input(AsyncPipe.Input):
        message: AsyncGenerator[str, None]
        context: str

    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the async vector storage pipe with necessary components and configurations.
        """
        logger.info(f"Initalizing an `DefaultRAGPipe` pipe.")
        if config and not isinstance(config, DefaultRAGPipe.GenerationConfig):
            raise ValueError(
                "Invalid configuration provided for `DefaultRAGPipe`."
            )

        super().__init__(
            config=config or DefaultRAGPipe.RAGConfig(),
            *args,
            **kwargs,
        )

    @property
    def do_await(self) -> bool:
        return True

    @property
    def type(self) -> PipeType:
        return PipeType.RAG

    @property
    def flow(self) -> PipeFlow:
        return PipeFlow.STANDARD

    async def _run_logic(
        self,
        input,  # : Input,
        context,  # : AsyncContext,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        search_results = []

        async for message in input.message:
            if not message:
                return "No message provided."
            else:
                return "good output.."

        await context.update(
            self.config.name, {"output": {"search_results": search_results}}
        )
