import random
from typing import Any, Optional

from ..logging.kv_logger import KVLoggingSingleton
from ..logging.run_manager import RunManager
from ..pipes.base_pipe import AsyncState
from .base_pipeline import Pipeline


class PipelineRouter(Pipeline):
    """PipelineRouter for routing to different pipelines based on weights."""

    def __init__(
        self,
        pipelines: dict[Pipeline, float],
        pipe_logger: Optional[KVLoggingSingleton] = None,
        run_manager: Optional[RunManager] = None,
    ):
        super().__init__(pipe_logger, run_manager)
        if not abs(sum(pipelines.values()) - 1.0) < 1e-6:
            raise ValueError("The weights must sum to 1")
        self.pipelines = pipelines

    async def run(
        self,
        input: Any,
        state: Optional[AsyncState] = None,
        streaming: bool = False,
        run_manager: Optional[RunManager] = None,
        *args: Any,
        **kwargs: Any,
    ):
        run_manager = run_manager or self.run_manager
        pipeline = self.select_pipeline()
        return await pipeline.run(
            input, state, streaming, run_manager, *args, **kwargs
        )

    def select_pipeline(self) -> Pipeline:
        pipelines, weights = zip(*self.pipelines.items())
        selected_pipeline = random.choices(pipelines, weights)[0]
        return selected_pipeline
