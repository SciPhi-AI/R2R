from abc import abstractmethod
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import AsyncState, CompletionProvider, DatabaseProvider
from core.base.abstractions import GenerationConfig
from core.base.pipes.base_pipe import AsyncPipe
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider


class GeneratorPipe(AsyncPipe):
    class PipeConfig(AsyncPipe.PipeConfig):
        name: str
        task_prompt: str
        system_prompt: str = "default_system"

    def __init__(
        self,
        llm_provider: CompletionProvider,
        database_provider: DatabaseProvider,
        config: AsyncPipe.PipeConfig,
        logging_provider: SqlitePersistentLoggingProvider,
        *args,
        **kwargs,
    ):
        super().__init__(
            config,
            logging_provider,
            *args,
            **kwargs,
        )
        self.llm_provider = llm_provider
        self.database_provider = database_provider

    @abstractmethod
    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        rag_generation_config: GenerationConfig,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, None]:
        pass
