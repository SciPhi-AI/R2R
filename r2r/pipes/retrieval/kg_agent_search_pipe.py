import logging
import uuid
from typing import Any, Optional

from r2r.base import (
    AsyncState,
    KGProvider,
    KGSearchSettings,
    KVLoggingSingleton,
    LLMProvider,
    PipeType,
    PromptProvider,
)

from ..abstractions.generator_pipe import GeneratorPipe

logger = logging.getLogger(__name__)


class KGAgentSearchPipe(GeneratorPipe):
    """
    Embeds and stores documents using a specified embedding model and database.
    """

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: LLMProvider,
        prompt_provider: PromptProvider,
        pipe_logger: Optional[KVLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        config: Optional[GeneratorPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the embedding pipe with necessary components and configurations.
        """
        super().__init__(
            llm_provider=llm_provider,
            prompt_provider=prompt_provider,
            type=type,
            config=config
            or GeneratorPipe.Config(
                name="kg_rag_pipe", task_prompt="kg_agent"
            ),
            pipe_logger=pipe_logger,
            *args,
            **kwargs,
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider
        self.pipe_run_info = None

    async def _run_logic(
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        kg_search_settings: KGSearchSettings,
        *args: Any,
        **kwargs: Any,
    ):
        async for message in input.message:
            # TODO - Remove hard code
            formatted_prompt = self.prompt_provider.get_prompt(
                "kg_agent", {"input": message}
            )
            messages = self._get_message_payload(formatted_prompt)

            result = self.llm_provider.get_completion(
                messages=messages,
                generation_config=kg_search_settings.agent_generation_config,
            )

            extraction = result.choices[0].message.content
            query = extraction.split("```cypher")[1].split("```")[0]
            result = self.kg_provider.structured_query(query)
            yield (query, result)

            await self.enqueue_log(
                run_id=run_id,
                key="kg_agent_response",
                value=extraction,
            )

            await self.enqueue_log(
                run_id=run_id,
                key="kg_agent_execution_result",
                value=result,
            )

    def _get_message_payload(self, message: str) -> dict:
        return [
            {
                "role": "system",
                "content": self.prompt_provider.get_prompt(
                    self.config.system_prompt,
                ),
            },
            {"role": "user", "content": message},
        ]
