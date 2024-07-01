import asyncio
import logging
from typing import Any, Optional

from ..base.abstractions.llm import GenerationConfig
from ..base.abstractions.search import KGSearchSettings, VectorSearchSettings
from ..base.logging.kv_logger import KVLoggingSingleton
from ..base.logging.run_manager import RunManager, manage_run
from ..base.pipeline.base_pipeline import AsyncPipeline
from ..base.pipes.base_pipe import AsyncPipe, AsyncState
from ..base.utils import to_async_generator

logger = logging.getLogger(__name__)


class RAGPipeline(AsyncPipeline):
    """A pipeline for RAG."""

    pipeline_type: str = "rag"

    def __init__(
        self,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        run_manager: Optional[RunManager] = None,
    ):
        super().__init__(pipe_logger, run_manager)
        self._search_pipeline = None
        self._rag_pipeline = None

    async def run(
        self,
        input: Any,
        state: Optional[AsyncState] = None,
        run_manager: Optional[RunManager] = None,
        log_run_info=True,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
        rag_generation_config: GenerationConfig = GenerationConfig(),
        *args: Any,
        **kwargs: Any,
    ):
        self.state = state or AsyncState()
        async with manage_run(run_manager, self.pipeline_type):
            if log_run_info:
                await run_manager.log_run_info(
                    key="pipeline_type",
                    value=self.pipeline_type,
                    is_info_log=True,
                )

            if not self._search_pipeline:
                raise ValueError(
                    "_search_pipeline must be set before running the RAG pipeline"
                )

            async def multi_query_generator(input):
                tasks = []
                async for query in input:
                    task = asyncio.create_task(
                        self._search_pipeline.run(
                            to_async_generator([query]),
                            state=state,
                            stream=False,  # do not stream the search results
                            run_manager=run_manager,
                            log_run_info=False,  # do not log the run info as it is already logged above
                            vector_search_settings=vector_search_settings,
                            kg_search_settings=kg_search_settings,
                            *args,
                            **kwargs,
                        )
                    )
                    tasks.append((query, task))

                for query, task in tasks:
                    yield (query, await task)

            rag_results = await self._rag_pipeline.run(
                input=multi_query_generator(input),
                state=state,
                stream=rag_generation_config.stream,
                run_manager=run_manager,
                log_run_info=False,
                rag_generation_config=rag_generation_config,
                *args,
                **kwargs,
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
        logger.debug(f"Setting search pipeline for the RAGPipeline")
        self._search_pipeline = _search_pipeline
