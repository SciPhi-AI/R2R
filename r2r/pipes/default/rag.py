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
        context: AsyncGenerator[str, None]

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

    def input_from_dict(self, input_dict: dict) -> Input:
        return DefaultRAGPipe.Input(**input_dict)

    async def _run_logic(
        self,
        input: Input,
        context: AsyncContext,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """
        Executes the async vector storage pipe: storing embeddings in the vector database.
        """
        print("run input = ", input)
        async with context.lock:
            print("context.data = ", context.data)
        return "x"
        # print("input = ", input)
        # await self._initialize_pipe(input, context, config_overrides=input.config_overrides or {})

        # search_results = []

        # if isinstance(input.message, AsyncGenerator):
        #     async for search_request in input.message:
        #         async for result in self.search(message=search_request):
        #             search_results.append(result)
        #             yield result
        # elif isinstance(input.message, str):
        #     async for result in self.search(message=input.message):
        #         search_results.append(result)
        #         yield result
        # else:
        #     raise TypeError("Input must be an AsyncGenerator or a string.")

        # await context.update(
        #     self.config.name, {"output": {"search_results": search_results}}
        # )
