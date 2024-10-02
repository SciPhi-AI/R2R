import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from core.base import (
    AsyncState,
    CompletionProvider,
    EmbeddingProvider,
    KGProvider,
    PipeType,
    PromptProvider,
    RunLoggingSingleton,
)
from core.base.abstractions import (
    KGCommunityResult,
    KGEntityResult,
    KGGlobalResult,
    KGRelationshipResult,
    KGSearchMethod,
    KGSearchResult,
    KGSearchResultType,
    KGSearchSettings,
    R2RException,
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
        config: GeneratorPipe.PipeConfig,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.INGESTOR,
        *args,
        **kwargs,
    ):
        """
        Initializes the embedding pipe with necessary components and configurations.
        """
        super().__init__(
            llm_provider,
            prompt_provider,
            config,
            type,
            pipe_logger,
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
            async for search_result in self.kg_provider.vector_query(  # type: ignore
                input,
                search_type=search_type,
                search_type_limits=kg_search_settings.local_search_limits[
                    search_type
                ],
                query_embedding=query_embedding,
                property_names=[
                    "name",
                    "description",
                    "extraction_ids",
                ],
                filters=kg_search_settings.filters,
            ):
                yield KGSearchResult(
                    content=KGEntityResult(
                        name=search_result["name"],
                        description=search_result["description"],
                    ),
                    method=KGSearchMethod.LOCAL,
                    result_type=KGSearchResultType.ENTITY,
                    extraction_ids=search_result["extraction_ids"],
                    metadata={"associated_query": message},
                )

            # relationship search
            # disabled for now. We will check evaluations and see if we need it
            # search_type = "__Relationship__"
            # async for search_result in self.kg_provider.vector_query(  # type: ignore
            #     input,
            #     search_type=search_type,
            #     search_type_limits=kg_search_settings.local_search_limits[
            #         search_type
            #     ],
            #     query_embedding=query_embedding,
            #     property_names=[
            #         "name",
            #         "description",
            #         "extraction_ids",
            #         "document_ids",
            #     ],
            # ):
            #     yield KGSearchResult(
            #         content=KGRelationshipResult(
            #             name=search_result["name"],
            #             description=search_result["description"],
            #         ),
            #         method=KGSearchMethod.LOCAL,
            #         result_type=KGSearchResultType.RELATIONSHIP,
            #         # extraction_ids=search_result["extraction_ids"],
            #         # document_ids=search_result["document_ids"],
            #         metadata={"associated_query": message},
            #     )

            # community search
            search_type = "__Community__"
            async for search_result in self.kg_provider.vector_query(  # type: ignore
                input,
                search_type=search_type,
                search_type_limits=kg_search_settings.local_search_limits[
                    search_type
                ],
                embedding_type="embedding",
                query_embedding=query_embedding,
                property_names=[
                    "community_number",
                    "name",
                    "findings",
                    "rating",
                    "rating_explanation",
                    "summary",
                ],
                filters=kg_search_settings.filters,
            ):
                yield KGSearchResult(
                    content=KGCommunityResult(
                        name=search_result["name"],
                        summary=search_result["summary"],
                        rating=search_result["rating"],
                        rating_explanation=search_result["rating_explanation"],
                        findings=search_result["findings"],
                    ),
                    method=KGSearchMethod.LOCAL,
                    result_type=KGSearchResultType.COMMUNITY,
                    metadata={
                        "associated_query": message,
                    },
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
            communities = self.kg_provider.get_communities(  # type: ignore
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
                        task_prompt_name=self.kg_provider.config.kg_search_settings.graphrag_map_system_prompt,
                        task_inputs={
                            "context_data": merged_report,
                            "input": message,
                        },
                    ),
                    generation_config=kg_search_settings.generation_config,
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
                    task_prompt_name=self.kg_provider.config.kg_search_settings.graphrag_reduce_system_prompt,
                    task_inputs={
                        "response_type": "multiple paragraphs",
                        "report_data": filtered_responses,
                        "input": message,
                    },
                ),
                generation_config=kg_search_settings.generation_config,
            )

            output_text = output.choices[0].message.content

            if not output_text:
                logger.warning(f"No output generated for query: {message}.")
                raise R2RException(
                    "No output generated for query.",
                    400,
                )

            yield KGSearchResult(
                content=KGGlobalResult(
                    name="Global Result", description=output_text
                ),
                method=KGSearchMethod.GLOBAL,
                metadata={"associated_query": message},
            )

    async def _run_logic(  # type: ignore
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: UUID,
        kg_search_settings: KGSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[KGSearchResult, None]:
        kg_search_type = kg_search_settings.kg_search_type

        # runs local and/or global search
        if kg_search_type == "local" or kg_search_type == "local_and_global":
            logger.info("Performing KG local search")
            async for result in self.local_search(
                input, state, run_id, kg_search_settings
            ):
                yield result

        if kg_search_type == "global" or kg_search_type == "local_and_global":
            logger.info("Performing KG global search")
            async for result in self.global_search(
                input, state, run_id, kg_search_settings
            ):
                yield result
