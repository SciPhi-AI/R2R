import logging
from typing import Any, AsyncGenerator, Optional

from r2r.core import (
    AsyncPipe,
    AsyncState,
    GenerationConfig,
    LLMProvider,
    PipeFlow,
    PipeType,
    PromptProvider,
)

from ...core.pipes.loggable import LoggableAsyncPipe

logger = logging.getLogger(__name__)


class DefaultQueryTransformPipe(LoggableAsyncPipe):
    class QueryTransformConfig(LoggableAsyncPipe.PipeConfig):
        name: str = "default_query_transform"
        num_answers: int = 3
        model: str = "gpt-3.5-turbo"
        system_prompt: str = "default_system_prompt"
        task_prompt: str = "hyde_prompt"
        generation_config: GenerationConfig = GenerationConfig(
            model="gpt-3.5-turbo"
        )

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        flow: PipeFlow = PipeFlow.FAN_OUT,
        type: PipeType = PipeType.TRANSFORM,
        config: Optional[QueryTransformConfig] = None,
        *args,
        **kwargs,
    ):
        logger.info(f"Initalizing an `DefaultQueryTransformPipe` pipe.")
        super().__init__(
            flow=flow,
            type=type,
            config=config or DefaultQueryTransformPipe.QueryTransformConfig(),
            *args,
            **kwargs,
        )
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        async for query in input.message:
            query_transform_request = self._get_llm_payload(query)

            response = self.llm_provider.get_completion(
                messages=query_transform_request,
                generation_config=self.config.generation_config,
            )
            content = self.llm_provider.extract_content(response)
            queries = content.split("\n\n")

            await state.update(
                self.config.name, {"output": {"queries": queries}}
            )

            for query in queries:
                yield query

    def _get_llm_payload(self, input: str) -> dict:
        return [
            {
                "role": "system",
                "content": self.prompt_provider.get_prompt(
                    self.config.system_prompt,
                ),
            },
            {
                "role": "user",
                "content": self.prompt_provider.get_prompt(
                    self.config.task_prompt,
                    inputs={
                        "message": input,
                        "num_answers": self.config.num_answers,
                    },
                ),
            },
        ]
