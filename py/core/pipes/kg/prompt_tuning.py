"""
Pipe to tune the prompt for the KG model.
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from core.base import (
    AsyncState,
    CompletionProvider,
    DatabaseProvider,
    R2RException,
)
from core.base.pipes.base_pipe import AsyncPipe
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider

logger = logging.getLogger()


class KGPromptTuningPipe(AsyncPipe):
    """
    A pipe to tune a prompt for a specific domain.
    """

    def __init__(
        self,
        database_provider: DatabaseProvider,
        llm_provider: CompletionProvider,
        config: AsyncPipe.PipeConfig,
        logging_provider: SqlitePersistentLoggingProvider,
        *args,
        **kwargs,
    ):
        super().__init__(
            logging_provider=logging_provider,
            config=config,
        )
        self.database_provider = database_provider
        self.llm_provider = llm_provider

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
            current_prompt = (
                await self.database_provider.get_all_prompts()
            ).get(prompt_name)

            if not current_prompt:
                raise R2RException(
                    message=f"Prompt {prompt_name} not found.", status_code=404
                )

            chunks = input.message["chunks"]

            # Add logging
            logger.info(f"Starting prompt tuning for {prompt_name}")

            tuned_prompt = await self.llm_provider.aget_completion(
                messages=await self.database_provider.prompt_handler.get_message_payload(
                    task_prompt_name="prompt_tuning_task",
                    task_inputs={
                        "prompt_template": current_prompt["template"],
                        "input_types": str(current_prompt["input_types"]),
                        "sample_data": chunks,
                    },
                ),
                generation_config=self.database_provider.config.graph_creation_settings.generation_config,
            )

            if not tuned_prompt:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate tuned prompt",
                )

            yield {"tuned_prompt": tuned_prompt.choices[0].message.content}

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error tuning prompt: {str(e)}",
            )
