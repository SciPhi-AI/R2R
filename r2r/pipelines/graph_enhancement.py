# pipeline for enriching knowledge graphs.

import asyncio
import logging
from asyncio import Queue
from typing import Any, Optional

from ..base.abstractions.search import (
    AggregateSearchResult,
    KGSearchSettings,
    VectorSearchSettings,
)
from ..base.logging.kv_logger import KVLoggingSingleton
from ..base.logging.run_manager import RunManager, manage_run
from ..base.pipeline.base_pipeline import AsyncPipeline, dequeue_requests
from ..base.pipes.base_pipe import AsyncPipe, AsyncState

logger = logging.getLogger(__name__)

class KGPipeline(AsyncPipeline):
    """A pipeline for enhancing the graph with communities, connnected components etc."""

    pipeline_type: str = "other"

    def __init__(
        self,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        run_manager: Optional[RunManager] = None,
    ):
        super().__init__(pipe_logger, run_manager)

    def add_pipe(
        self,
        pipe: AsyncPipe,
        *args,
        **kwargs,
    ) -> None:
        logger.debug(f"Adding pipe {pipe.config.name} to the KGPipeline")
        super().add_pipe(pipe, *args, **kwargs)