import asyncio
import logging
from typing import Any, Optional

from ..base.abstractions.llm import GenerationConfig
from ..base.abstractions.search import KGSearchSettings, VectorSearchSettings
from ..base.logging import RunType
from ..base.logging.run_logger import RunLoggingSingleton
from ..base.logging.run_manager import RunManager, manage_run
from ..base.pipeline.base_pipeline import AsyncPipeline
from ..base.pipes.base_pipe import AsyncPipe, AsyncState
from ..base.utils import to_async_generator

logger = logging.getLogger(__name__)


class RAGPipeline(AsyncPipeline):
    """A pipeline for RAG."""

    def __init__(
        self,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        run_manager: Optional[RunManager] = None,
    ):
        super().__init__(pipe_logger, run_manager)
        self._search_pipeline: Optional[AsyncPipeline] = None
        self._rag_pipeline: Optional[AsyncPipeline] = None

    async def run(  # type: ignore
        self,
        input: Any,
        state: Optional[AsyncState],
        run_manager: Optional[RunManager] = None,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
        rag_generation_config: GenerationConfig = GenerationConfig(),
        *args: Any,
        **kwargs: Any,
    ):
        if not self._rag_pipeline:
            raise ValueError(
                "`_rag_pipeline` must be set before running the RAG pipeline"
            )
        self.state = state or AsyncState()
        # TODO - This feels anti-pattern.
        run_manager = (
            run_manager or self.run_manager or RunManager(self.pipe_logger)
        )
        async with manage_run(run_manager, RunType.RETRIEVAL):
            if not self._search_pipeline:
                raise ValueError(
                    "`_search_pipeline` must be set before running the RAG pipeline"
                )

            async def multi_query_generator(input):
                tasks = []
                async for query in input:
                    input_kwargs = {
                        **kwargs,
                        "vector_search_settings": vector_search_settings,
                        "kg_search_settings": kg_search_settings,
                    }
                    task = asyncio.create_task(
                        self._search_pipeline.run(
                            to_async_generator([query]),
                            state,
                            False,
                            run_manager,
                            *args,
                            **input_kwargs,
                        )
                    )
                    tasks.append((query, task))

                for query, task in tasks:
                    yield (query, await task)

            input_kwargs = {
                **kwargs,
                "rag_generation_config": rag_generation_config,
            }

            print("_input_kwargs_=", input_kwargs)
            print("_kwargs_=", kwargs)
            rag_results = await self._rag_pipeline.run(
                multi_query_generator(input),
                state,
                rag_generation_config.stream,
                run_manager,
                *args,
                **input_kwargs,
            )
            return rag_results

    def add_pipe(
        self,
        pipe: AsyncPipe,
        add_upstream_outputs: Optional[list[dict[str, str]]] = None,
        rag_pipe: bool = True,
        *args,
        **kwargs,
    ) -> None:
        logger.debug(f"Adding pipe {pipe.config.name} to the RAGPipeline")
        if not rag_pipe:
            raise ValueError(
                "Only pipes that are part of the RAG pipeline can be added to the RAG pipeline"
            )
        if not self._rag_pipeline:
            self._rag_pipeline = AsyncPipeline()
        self._rag_pipeline.add_pipe(
            pipe, add_upstream_outputs, *args, **kwargs
        )

    def set_search_pipeline(
        self,
        _search_pipeline: AsyncPipeline,
        *args,
        **kwargs,
    ) -> None:
        logger.debug("Setting search pipeline for the RAGPipeline")
        self._search_pipeline = _search_pipeline
