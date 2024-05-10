import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import AsyncContext, AsyncPipe, PipeFlow, PipeType

logger = logging.getLogger(__name__)


class DefaultRAGPipe(AsyncPipe):
    class Input(AsyncPipe.Input):
        message: AsyncGenerator[str, None]
        context: str

    def __init__(
        self,
        flow: PipeFlow = PipeFlow.STANDARD,
        type: PipeType = PipeType.GENERATION,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        super().__init__(
            flow=flow,
            type=type,
            config=config or AsyncPipe.PipeConfig(name="default_rag"),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self,
        input: Input,
        context: AsyncContext,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        search_results = []
        # print('input.message = ', input.message)
        async for message in input.message:
            if not message:
                yield "No message provided."
            else:
                yield "good output.."
        # yield input.message
        await context.update(
            self.config.name, {"output": {"search_results": search_results}}
        )
