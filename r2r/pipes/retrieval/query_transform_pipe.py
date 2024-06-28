import logging
import uuid
from typing import Any, AsyncGenerator, Optional

from r2r.base import (
    AsyncPipe,
    AsyncState,
    LLMProvider,
    PipeType,
    PromptProvider,
)
from r2r.base.abstractions.llm import GenerationConfig

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
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        type: PipeType = PipeType.TRANSFORM,
        config: Optional[QueryTransformConfig] = None,
        *args,
        **kwargs,
    ):
        logger.info(f"Initalizing an `QueryTransformPipe` pipe.")
        super().__init__(
            llm_provider=llm_provider,
            prompt_provider=prompt_provider,
            type=type,
            config=config or QueryTransformPipe.QueryTransformConfig(),
            *args,
            **kwargs,
        )

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        query_transform_generation_config: GenerationConfig,
        num_query_xf_outputs: int = 3,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        async for query in input.message:
            logger.info(
                f"Transforming query: {query} into {num_query_xf_outputs} outputs with {self.config.task_prompt}."
            )

            query_transform_request = self._get_message_payload(
                query, num_outputs=num_query_xf_outputs
            )

            response = self.llm_provider.get_completion(
                messages=query_transform_request,
                generation_config=query_transform_generation_config,
            )
            content = self.llm_provider.extract_content(response)
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

    def _get_message_payload(self, input: str, num_outputs: int) -> dict:
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
                        "num_outputs": num_outputs,
                    },
                ),
            },
        ]
