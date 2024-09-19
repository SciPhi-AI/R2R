import asyncio
import json
import logging
from typing import Any, Optional, AsyncGenerator
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
    KGSearchResult,
    KGGlobalResult,
    KGSearchMethod,
    KGSearchResultType,
    KGEntityResult,
    KGRelationshipResult,
    KGCommunityResult,
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
    ) -> AsyncGenerator[KGSearchResult, None]:
        # search over communities and
        # do 3 searches. One over entities, one over relationships, one over communities

        async for message in input.message:
            query_embedding = (
                await self.embedding_provider.async_get_embedding(message)
            )

            # entity search
            search_type = "__Entity__"
            async for search_result in self.kg_provider.vector_query(
                input,
                search_type=search_type,
                search_type_limits=kg_search_settings.local_search_limits[
                    search_type
                ],
                query_embedding=query_embedding,
                property_names=[
                    "name",
                    "description",
                    "fragment_ids",
                    "document_ids",
                ],
            ):
                print(search_result)
                yield KGSearchResult(
                    content=KGEntityResult(
                        name=search_result["name"],
                        description=search_result["description"],
                    ),
                    method=KGSearchMethod.LOCAL,
                    result_type=KGSearchResultType.ENTITY,
                    fragment_ids=search_result["fragment_ids"],
                    document_ids=search_result["document_ids"],
                    metadata={"associated_query": message},
                )

            # relationship search
            search_type = "__Relationship__"
            async for search_result in self.kg_provider.vector_query(
                input,
                search_type=search_type,
                search_type_limits=kg_search_settings.local_search_limits[
                    search_type
                ],
                query_embedding=query_embedding,
                property_names=[
                    "name",
                    "description",
                    "fragment_ids",
                    "document_ids",
                ],
            ):
                yield KGSearchResult(
                    content=KGRelationshipResult(
                        name=search_result["name"],
                        description=search_result["description"],
                    ),
                    method=KGSearchMethod.LOCAL,
                    result_type=KGSearchResultType.RELATIONSHIP,
                    fragment_ids=search_result["fragment_ids"],
                    document_ids=search_result["document_ids"],
                    metadata={"associated_query": message},
                )

            # community search
            search_type = "__Community__"
            async for search_result in self.kg_provider.vector_query(
                input,
                search_type=search_type,
                search_type_limits=kg_search_settings.local_search_limits[
                    search_type
                ],
                embedding_type="summary_embedding",
                query_embedding=query_embedding,
                property_names=["title", "summary"],
            ):

                summary = search_result["summary"]

                # try loading it as a json
                try:
                    summary_json = json.loads(summary)
                    description = summary_json.get("summary", "")
                    name = summary_json.get("title", "")

                    description += "\n\n" + "\n".join(
                        [
                            finding["summary"]
                            for finding in summary_json.get("findings", [])
                        ]
                    )

                except json.JSONDecodeError:
                    logger.warning(f"Summary is not valid JSON")
                    continue

                yield KGSearchResult(
                    content=KGCommunityResult(
                        name=name, description=description
                    ),
                    method=KGSearchMethod.LOCAL,
                    result_type=KGSearchResultType.COMMUNITY,
                    metadata={"associated_query": message},
                )

    async def global_search(
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: UUID,
        kg_search_settings: KGSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[KGSearchResult, None]:
        # map reduce
        async for message in input.message:
            map_responses = []
            communities = self.kg_provider.get_communities(
                level=kg_search_settings.kg_search_level
            )

            if len(communities) == 0:
                raise R2RException(
                    "No communities found. Please make sure you have run the KG enrichment step before running the search: r2r create-graph and r2r enrich-graph",
                    400,
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

            output = output.choices[0].message.content

            yield KGSearchResult(
                content=KGGlobalResult(
                    name="Global Result", description=output
                ),
                method=KGSearchMethod.GLOBAL,
                metadata={'associated_query': message},
            )

    async def _run_logic(
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: UUID,
        kg_search_settings: KGSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[KGSearchResult, None]:

        kg_search_type = kg_search_settings.kg_search_type

        if kg_search_type == "local":
            logger.info("Performing KG local search")
            async for result in self.local_search(
                input, state, run_id, kg_search_settings
            ):
                yield result

        else:
            logger.info("Performing KG global search")
            async for result in self.global_search(
                input, state, run_id, kg_search_settings
            ):
                yield result
