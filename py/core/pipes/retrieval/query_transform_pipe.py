import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from core.base import (
    AsyncPipe,
    AsyncState,
    CompletionProvider,
    PipeType,
    PromptProvider,
)
from core.base.abstractions import GenerationConfig

from ..abstractions.generator_pipe import GeneratorPipe

logger = logging.getLogger(__name__)


class QueryTransformPipe(GeneratorPipe):
    class QueryTransformConfig(GeneratorPipe.PipeConfig):
        name: str = "default_query_transform"
        system_prompt: str = "default_system"
        task_prompt: str = "hyde"

    class Input(GeneratorPipe.Input):
        message: AsyncGenerator[str, None]

    def __init__(
        self,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        config: QueryTransformConfig,
        type: PipeType = PipeType.TRANSFORM,
        *args,
        **kwargs,
    ):
        logger.info(f"Initalizing an `QueryTransformPipe` pipe.")
        super().__init__(
            llm_provider,
            prompt_provider,
            config,
            type,
            *args,
            **kwargs,
        )
        self._config: QueryTransformPipe.QueryTransformConfig = config

    @property
    def config(self) -> QueryTransformConfig:  # type: ignore
        return self._config

    async def _run_logic(  # type: ignore
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        query_transform_generation_config: GenerationConfig,
        num_query_xf_outputs: int = 3,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        async for query in input.message:
            logger.info(
                f"Transforming query: {query} into {num_query_xf_outputs} outputs with {self.config.task_prompt}."
            )

            query_transform_request = (
                self.prompt_provider._get_message_payload(
                    system_prompt_name=self.config.system_prompt,
                    task_prompt_name=self.config.task_prompt,
                    task_inputs={
                        "message": query,
                        "num_outputs": num_query_xf_outputs,
                    },
                )
            )

            response = await self.llm_provider.aget_completion(
                messages=query_transform_request,
                generation_config=query_transform_generation_config,
            )
            content = response.choices[0].message.content
            if not content:
                logger.error(f"Failed to transform query: {query}. Skipping.")
                raise ValueError(f"Failed to transform query: {query}.")
            outputs = content.split("\n")
            outputs = [
                output.strip() for output in outputs if output.strip() != ""
            ]
            await state.update(
                self.config.name, {"output": {"outputs": outputs}}
            )

            for output in outputs:
                logger.info(f"Yielding transformed output: {output}")
                yield output
