import logging
from typing import Any, Optional

from ..abstractions.llm import GenerationConfig
from ..abstractions.search import KGSearchSettings, VectorSearchSettings
from ..logging.kv_logger import KVLoggingSingleton
from ..logging.run_manager import RunManager, manage_run
from ..pipes.base_pipe import AsyncPipe, AsyncState
from .base_pipeline import Pipeline

logger = logging.getLogger(__name__)


class RAGPipeline(Pipeline):
    """A pipeline for RAG."""

    pipeline_type: str = "rag"

    def __init__(
        self,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        run_manager: Optional[RunManager] = None,
    ):
        super().__init__(pipe_logger, run_manager)
        self.parsing_pipe = None
        self.search_pipeline = None

    async def run(
        self,
        input: Any,
        state: Optional[AsyncState] = None,
        streaming: bool = False,
        run_manager: Optional[RunManager] = None,
        vector_search_settings: VectorSearchSettings = VectorSearchSettings(),
        kg_search_settings: KGSearchSettings = KGSearchSettings(),
        rag_generation_config: GenerationConfig = GenerationConfig(),
        *args: Any,
        **kwargs: Any,
    ):
        self.state = state or AsyncState()

        async with manage_run(run_manager, self.pipeline_type):
            await run_manager.log_run_info(
                key="pipeline_type",
                value=self.pipeline_type,
                is_info_log=True,
            )

            if not self.search_pipeline:
                raise ValueError(
                    "search_pipeline must be set before running the RAG pipeline"
                )

            search_results = await self.search_pipeline.run(
                input,
                state,
                streaming,
                run_manager,
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
                *args,
                **kwargs,
            )
            print("search_results = ", search_results)
            return search_results

    def add_pipe(
        self,
        pipe: AsyncPipe,
        add_upstream_outputs: Optional[list[dict[str, str]]] = None,
        *args,
        **kwargs,
    ) -> None:
        logger.debug(f"Adding pipe {pipe.config.name} to the RAGPipeline")
        return super().add_pipe(pipe, add_upstream_outputs, *args, **kwargs)

    def set_search_pipeline(
        self,
        search_pipeline: Pipeline,
        *args,
        **kwargs,
    ) -> None:
        logger.debug(f"Setting search pipeline for the RAGPipeline")
        self.search_pipeline = search_pipeline
