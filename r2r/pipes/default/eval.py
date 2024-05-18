import logging
import random
from typing import Any, AsyncGenerator, Optional

from r2r import (
    AsyncState,
    EvalProvider,
    LLMChatCompletion,
    LoggableAsyncPipe,
    PipeType,
)

logger = logging.getLogger(__name__)


class DefaultEvalPipe(LoggableAsyncPipe):
    class Input(LoggableAsyncPipe.Input):
        query: str
        context: str
        completion: LLMChatCompletion

    def __init__(
        self,
        eval_provider: EvalProvider,
        type: PipeType = PipeType.EVAL,
        config: Optional[LoggableAsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        self.eval_provider = eval_provider
        super().__init__(
            type=type,
            config=config
            or LoggableAsyncPipe.PipeConfig(name="default_eval_pipe"),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self, input: Input, state: AsyncState, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[LLMChatCompletion, None]:
        logger.debug(
            f"Running the `EvaluationPipeline` with id={self.run_info}."
        )

        if random.random() < self.eval_provider.config.sampling_fraction:
            evaluation_result = await self.evaluate(
                input.query, input.context, input.completion
            )
            yield evaluation_result
        else:
            yield None
