import json
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

import asyncio
from ..abstractions.generator_pipe import GeneratorPipe

logger = logging.getLogger(__name__)


class KGSearchSearchPipe(GeneratorPipe):
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
                name="kg_rag_pipe", task_prompt="kg_search"
            ),
            pipe_logger=pipe_logger,
            *args,
            **kwargs,
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider
        self.pipe_run_info = None

    async def local_search(self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        kg_search_settings: KGSearchSettings,
        *args: Any,
        **kwargs: Any,
    ):
        async for message in input.message:

            if not kg_search_settings.entity_types:
                messages = self.prompt_provider._get_message_payload(
                    task_prompt_name="kg_search",
                    task_inputs={"input": message},
                )
            else:
                messages = self.prompt_provider._get_message_payload(
                    task_prompt_name="kg_search_with_spec",
                    task_inputs={
                        "input": message,
                        "entity_types": str(kg_search_settings.entity_types),
                        "relations": str(kg_search_settings.relationships),
                    },
                )

            result = await self.llm_provider.aget_completion(
                messages=messages,
                generation_config=kg_search_settings.kg_search_generation_config,
            )

            extraction = result.choices[0].message.content
            query = extraction.split("```cypher")[1].split("```")[0]
            result = self.kg_provider.structured_query(query)
            yield (query, result)

            await self.enqueue_log(
                run_id=run_id,
                key="kg_search_response",
                value=extraction,
            )

            await self.enqueue_log(
                run_id=run_id,
                key="kg_search_execution_result",
                value=result,
            )

    def filter_responses(self, map_responses):

        responses = [json.loads(response) for response in map_responses]
        responses = [item for sublist in responses for item in sublist]

        responses = [response for response in responses if response['score'] > 0]
        responses = sorted(responses, key=lambda x: x['score'], reverse=True)
        return responses
    
    async def global_search(self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        kg_search_settings: KGSearchSettings,
        *args: Any,
        **kwargs: Any,
    ):
        # map reduce
        async for message in input.message:
            map_responses = []
            communities = self.kg_provider.get_all_communities()
            
            async def process_community(community):
                community_description = self.kg_provider.get_community_description(community)
                truncated_description = community_description[:kg_search_settings.max_community_description_length]
                
                return await self.llm_provider.aget_completion(
                    messages=self.prompt_provider._get_message_payload(
                        task_prompt_name="map_system_prompt",
                        task_inputs={
                            "context_data": truncated_description,
                            "input": message,
                        },
                    ),
                    generation_config=kg_search_settings.kg_search_generation_config,
                )

            # Use asyncio.gather to process all communities concurrently
            map_responses = await asyncio.gather(*[process_community(community) for community in communities])

            # Filter only the relevant responses
            filtered_responses = self.filter_responses(map_responses)

            # reducing the outputs
            output = await self.llm_provider.aget_completion(
                messages=self.prompt_provider._get_message_payload(
                    task_prompt_name="reduce_system_prompt",
                    task_inputs={
                        "response_type": 'multiple paragraphs',
                        "report_data": filtered_responses,
                        "input": message,
                    },
                ),
                generation_config=kg_search_settings.kg_search_generation_config,
            )
            yield output

    async def _run_logic(
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        kg_search_settings: KGSearchSettings,
        *args: Any,
        **kwargs: Any,
    ):

        kg_search_type = kg_search_settings.kg_search_type
        if kg_search_type == 'local':
            async for query, result in self.local_search(input, state, run_id, kg_search_settings):
                yield (query, result)

        else:
            async for query, result in self.global_search(input, state, run_id, kg_search_settings):
                yield (query, result)