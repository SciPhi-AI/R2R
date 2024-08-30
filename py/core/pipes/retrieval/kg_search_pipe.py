import asyncio
import json
import logging
from typing import Any, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    CompletionProvider,
    EmbeddingProvider,
    KGProvider,
    KGSearchSettings,
    PipeType,
    PromptProvider,
    R2RException,
    RunLoggingSingleton,
)
from core.base.abstractions.search import (
    KGGlobalSearchResult,
    KGLocalSearchResult,
    KGSearchResult,
)

from ..abstractions.generator_pipe import GeneratorPipe

logger = logging.getLogger(__name__)


class KGSearchSearchPipe(GeneratorPipe):
    """
    Embeds and stores documents using a specified embedding model and database.
    """

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        embedding_provider: EmbeddingProvider,
        pipe_logger: Optional[RunLoggingSingleton] = None,
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
        self.embedding_provider = embedding_provider
        self.pipe_run_info = None

    def filter_responses(self, map_responses):
        filtered_responses = []
        for response in map_responses:
            try:
                parsed_response = json.loads(response)
                for item in parsed_response["points"]:
                    try:
                        if item["score"] > 0:
                            filtered_responses.append(item)
                    except KeyError:
                        # Skip this item if it doesn't have a 'score' key
                        logger.warning(f"Item in response missing 'score' key")
                        continue
            except json.JSONDecodeError:
                logger.warning(
                    f"Response is not valid JSON: {response[:100]}..."
                )
                continue
            except KeyError:
                logger.warning(
                    f"Response is missing 'points' key: {response[:100]}..."
                )
                continue

        filtered_responses = sorted(
            filtered_responses, key=lambda x: x["score"], reverse=True
        )

        responses = "\n".join(
            [
                response.get("description", "")
                for response in filtered_responses
            ]
        )
        return responses

    async def local_search(
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: UUID,
        kg_search_settings: KGSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> KGLocalSearchResult:
        # search over communities and
        # do 3 searches. One over entities, one over relationships, one over communities

        async for message in input.message:
            query_embedding = (
                await self.embedding_provider.async_get_embedding(message)
            )

            all_search_results = []
            for search_type in [
                "__Entity__",
                "__Relationship__",
                "__Community__",
            ]:
                search_result = self.kg_provider.vector_query(
                    input,
                    search_type=search_type,
                    search_type_limits=kg_search_settings.local_search_limits[
                        search_type
                    ],
                    query_embedding=query_embedding,
                )
                all_search_results.append(search_result)

            if len(all_search_results[0]) == 0:
                raise R2RException(
                    "No search results found. Please make sure you have run the KG enrichment step before running the search: r2r enrich-graph",
                    400,
                )

            yield KGLocalSearchResult(
                query=message,
                entities=all_search_results[0],
                relationships=all_search_results[1],
                communities=all_search_results[2],
            )

    async def global_search(
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: UUID,
        kg_search_settings: KGSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> KGGlobalSearchResult:
        # map reduce
        async for message in input.message:
            map_responses = []
            communities = self.kg_provider.get_communities(
                level=kg_search_settings.kg_search_level
            )

            async def preprocess_communities(communities):
                merged_report = ""
                for community in communities:
                    community_report = community.summary
                    if (
                        len(merged_report) + len(community_report)
                        > kg_search_settings.max_community_description_length
                    ):
                        yield merged_report.strip()
                        merged_report = ""
                    merged_report += community_report + "\n\n"
                if merged_report:
                    yield merged_report.strip()

            async def process_community(merged_report):
                output = await self.llm_provider.aget_completion(
                    messages=self.prompt_provider._get_message_payload(
                        task_prompt_name="graphrag_map_system_prompt",
                        task_inputs={
                            "context_data": merged_report,
                            "input": message,
                        },
                    ),
                    generation_config=kg_search_settings.kg_search_generation_config,
                )

                return output.choices[0].message.content

            preprocessed_reports = [
                merged_report
                async for merged_report in preprocess_communities(communities)
            ]

            # Use asyncio.gather to process all preprocessed community reports concurrently
            logger.info(
                f"Processing {len(communities)} communities, {len(preprocessed_reports)} reports, Max LLM queries = {kg_search_settings.max_llm_queries_for_global_search}"
            )

            map_responses = await asyncio.gather(
                *[
                    process_community(report)
                    for report in preprocessed_reports[
                        : kg_search_settings.max_llm_queries_for_global_search
                    ]
                ]
            )
            # Filter only the relevant responses
            filtered_responses = self.filter_responses(map_responses)

            # reducing the outputs
            output = await self.llm_provider.aget_completion(
                messages=self.prompt_provider._get_message_payload(
                    task_prompt_name="graphrag_reduce_system_prompt",
                    task_inputs={
                        "response_type": "multiple paragraphs",
                        "report_data": filtered_responses,
                        "input": message,
                    },
                ),
                generation_config=kg_search_settings.kg_search_generation_config,
            )

            output = [output.choices[0].message.content]

            yield KGGlobalSearchResult(query=message, search_result=output)

    async def _run_logic(
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: UUID,
        kg_search_settings: KGSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> KGSearchResult:

        logger.info("Performing global search")
        kg_search_type = kg_search_settings.kg_search_type

        if kg_search_type == "local":
            async for result in self.local_search(
                input, state, run_id, kg_search_settings
            ):
                yield KGSearchResult(local_result=result)

        else:
            async for result in self.global_search(
                input, state, run_id, kg_search_settings
            ):
                yield KGSearchResult(global_result=result)
