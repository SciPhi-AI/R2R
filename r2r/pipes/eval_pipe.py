import logging
import random
import uuid
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

from r2r import (
    AsyncState,
    EvalProvider,
    GenerationConfig,
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
        self,
        input: Input,
        state: AsyncState,
        run_id: uuid.UUID,
        eval_generation_config: GenerationConfig,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[LLMChatCompletion, None]:
        async for item in input.message:
            yield self.eval_provider.evaluate(
                item.query,
                item.context,
                item.completion,
                eval_generation_config,
            )
