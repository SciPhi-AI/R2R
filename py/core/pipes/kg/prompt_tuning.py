"""
Pipe to tune the prompt for the KG model.
"""

import logging
from typing import Any, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    CompletionProvider,
    KGProvider,
    PipeType,
    PromptProvider,
    R2RException,
    R2RLoggingProvider,
)
from core.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger()


class KGPromptTuningPipe(AsyncPipe):
    """
    A pipe to tune a prompt for a specific domain.
    """

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        config: AsyncPipe.PipeConfig,
        pipe_logger: Optional[R2RLoggingProvider] = None,
        type: PipeType = PipeType.OTHER,
        *args,
        **kwargs,
    ):
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config,
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ):
        try:
            prompt_name = input.message["prompt_name"]
            current_prompt = self.prompt_provider.get_all_prompts().get(
                prompt_name
            )

            if not current_prompt:
                raise R2RException(
                    message=f"Prompt {prompt_name} not found.", status_code=404
                )

            chunks = input.message["chunks"]

            # Add logging
            logger.info(f"Starting prompt tuning for {prompt_name}")

            tuned_prompt = await self.llm_provider.aget_completion(
                messages=await self.prompt_provider._get_message_payload(
                    task_prompt_name="prompt_tuning_task",
                    task_inputs={
                        "prompt_template": current_prompt.template,
                        "input_types": str(current_prompt.input_types),
                        "sample_data": chunks,
                    },
                ),
                generation_config=self.kg_provider.config.kg_creation_settings.generation_config,
            )

            if not tuned_prompt:
                raise R2RException(
                    message="Failed to generate tuned prompt", status_code=500
                )

            yield {"tuned_prompt": tuned_prompt.choices[0].message.content}

        except Exception as e:
            logger.error(f"Error in prompt tuning: {str(e)}")
            raise R2RException(
                message=f"Error tuning prompt: {str(e)}", status_code=500
            )
