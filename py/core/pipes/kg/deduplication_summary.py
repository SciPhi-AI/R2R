from core.base.pipes import AsyncPipe
from core.base.providers import KGProvider, PromptProvider, CompletionProvider, EmbeddingProvider
from typing import Optional

from core.base.logging import R2RLoggingProvider
from core.base.pipes import AsyncPipe, PipeType


class KGEntityDeduplicationSummaryPipe(AsyncPipe):
    def __init__(self, kg_provider: KGProvider, prompt_provider: PromptProvider, llm_provider: CompletionProvider, embedding_provider: EmbeddingProvider, config: AsyncPipe.PipeConfig, pipe_logger: Optional[R2RLoggingProvider] = None, type: PipeType = PipeType.OTHER, **kwargs):
        super().__init__(pipe_logger=pipe_logger, type=type, config=config, **kwargs)
        self.kg_provider = kg_provider
        self.prompt_provider = prompt_provider
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def _run_logic(self, **kwargs) -> dict:
        pass

