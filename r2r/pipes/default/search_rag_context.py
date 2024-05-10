import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import AsyncContext, AsyncPipe, PipeFlow, PipeType

from ..abstractions.aggregator import AggregatorPipe

logger = logging.getLogger(__name__)


class DefaultSearchRAGContextPipe(AggregatorPipe):
    def __init__(
        self,
        flow: PipeFlow = PipeFlow.FAN_IN,
        type: PipeType = PipeType.AGGREGATE,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        logger.info(f"Initalizing an `DefaultSearchRAGContextPipe` pipe.")
        super().__init__(
            flow=flow,
            type=type,
            config=config
            or AsyncPipe.PipeConfig(name="default_search_rag_context"),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        context: AsyncContext,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        await self.aggregate(input, context)
        if len(self.results) > 0:
            rag_context = "\n\n".join([str(ele) for ele in self.results])

        else:
            rag_context = "No results found."

        await context.update(
            self.config.name, {"output": {"rag_context": rag_context}}
        )
        yield rag_context
