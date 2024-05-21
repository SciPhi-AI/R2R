import logging
import random
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

from r2r import (
    AsyncState,
    EvalProvider,
    LLMChatCompletion,
    LoggableAsyncPipe,
    PipeType,
)

logger = logging.getLogger(__name__)


class R2REvalPipe(LoggableAsyncPipe):
    class EvalPayload(BaseModel):
        query: str
        context: str
        completion: str

    class Input(LoggableAsyncPipe.Input):
        message: AsyncGenerator["R2REvalPipe.EvalPayload", None]

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
        async for item in input.message:
            if random.random() < self.eval_provider.config.sampling_fraction:
                yield self.eval_provider.evaluate(
                    item.query, item.context, item.completion
                )
            else:
                yield None
