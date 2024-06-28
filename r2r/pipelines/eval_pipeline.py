import logging
from typing import Any, Optional

from r2r.base.logging.run_manager import RunManager
from r2r.base.pipeline.base_pipeline import AsyncPipeline
from r2r.base.pipes.base_pipe import AsyncPipe, AsyncState

logger = logging.getLogger(__name__)


class EvalPipeline(AsyncPipeline):
    """A pipeline for evaluation."""

    pipeline_type: str = "eval"

    async def run(
        self,
        input: Any,
        state: Optional[AsyncState] = None,
        stream: bool = False,
        run_manager: Optional[RunManager] = None,
        *args: Any,
        **kwargs: Any,
    ):
        return await super().run(
            input, state, stream, run_manager, *args, **kwargs
        )

    def add_pipe(
        self,
        pipe: AsyncPipe,
        add_upstream_outputs: Optional[list[dict[str, str]]] = None,
        *args,
        **kwargs,
    ) -> None:
        logger.debug(f"Adding pipe {pipe.config.name} to the EvalPipeline")
        return super().add_pipe(pipe, add_upstream_outputs, *args, **kwargs)
