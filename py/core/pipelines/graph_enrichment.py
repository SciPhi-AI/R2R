import logging
from typing import Optional

from ..base.logging.r2r_logger import R2RLoggingProvider
from ..base.logging.run_manager import RunManager
from ..base.pipeline.base_pipeline import AsyncPipeline
from ..base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger()


class KGEnrichmentPipeline(AsyncPipeline):
    """A pipeline for enhancing the graph with communities, connnected components etc."""

    pipeline_type: str = "other"

    def __init__(
        self,
        pipe_logger: Optional[R2RLoggingProvider] = None,
        run_manager: Optional[RunManager] = None,
    ):
        super().__init__(pipe_logger, run_manager)

    def add_pipe(
        self,
        pipe: AsyncPipe,
        *args,
        **kwargs,
    ) -> None:
        logger.debug(
            f"Adding pipe {pipe.config.name} to the KGEnrichmentPipeline"
        )
        super().add_pipe(pipe, *args, **kwargs)
