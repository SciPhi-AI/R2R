import logging
import uuid
from typing import Any, AsyncGenerator, Optional

from pydantic import BaseModel

from r2r import (
    AsyncState,
    EvalProvider,
    LLMChatCompletion,
    LoggableAsyncPipe,
    PipeType,
)
from r2r.core.abstractions.llm import GenerationConfig

logger = logging.getLogger(__name__)


class EvalPipe(LoggableAsyncPipe):
    class EvalPayload(BaseModel):
        query: str
        context: str
        completion: str

    class Input(LoggableAsyncPipe.Input):
        message: AsyncGenerator["EvalPipe.EvalPayload", None]

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
