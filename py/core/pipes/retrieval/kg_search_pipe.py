import json
import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from core.base import (
    AsyncState,
    CompletionProvider,
    DatabaseProvider,
    EmbeddingProvider,
)
from core.base.abstractions import (
    GraphSearchResult,
    GraphSearchSettings,
    KGCommunityResult,
    KGEntityResult,
    KGRelationshipResult,
    KGSearchResultType,
    SearchSettings,
)
from core.providers.logger.r2r_logger import SqlitePersistentLoggingProvider

from ..abstractions.generator_pipe import GeneratorPipe

logger = logging.getLogger()


class KGSearchSearchPipe(GeneratorPipe):
    """
    Embeds and stores documents using a specified embedding model and database.
    """

    def __init__(
        self,
        llm_provider: CompletionProvider,
        database_provider: DatabaseProvider,
        embedding_provider: EmbeddingProvider,
        config: GeneratorPipe.PipeConfig,
        logging_provider: SqlitePersistentLoggingProvider,
        *args,
        **kwargs,
    ):
        """
        Initializes the embedding pipe with necessary components and configurations.
        """
        super().__init__(
            llm_provider,
            database_provider,
            config,
            logging_provider,
            *args,
            **kwargs,
        )
        self.database_provider = database_provider
        self.llm_provider = llm_provider
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

    async def search(
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: UUID,
        search_settings: SearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[GraphSearchResult, None]:
        if search_settings.graph_settings.enabled == False:
            return

        async for message in input.message:
            query_embedding = (
                await self.embedding_provider.async_get_embedding(message)
            )

            # entity search
            search_type = "entities"
            base_limit = search_settings.limit

            if search_type not in search_settings.graph_settings.limits:
                logger.warning(
                    f"No limit set for graph search type {search_type}, defaulting to global settings limit of {base_limit}"
                )
            async for search_result in self.database_provider.graph_handler.graph_search(  # type: ignore
                message,
                search_type=search_type,
                limit=search_settings.graph_settings.limits.get(
                    search_type, base_limit
                ),
                query_embedding=query_embedding,
                property_names=[
                    "name",
                    "description",
                    "chunk_ids",
                ],
                filters=search_settings.filters,
            ):
                yield GraphSearchResult(
                    content=KGEntityResult(
                        name=search_result["name"],
                        description=search_result["description"],
                    ),
                    result_type=KGSearchResultType.ENTITY,
                    score=(
                        search_result["similarity_score"]
                        if search_settings.include_scores
                        else None
                    ),
                    # chunk_ids=search_result["chunk_ids"],
                    metadata=(
                        {
                            "associated_query": message,
                            **(search_result["metadata"] or {}),
                        }
                        if search_settings.include_metadatas
                        else None
                    ),
                )

            # # relationship search
            # # disabled for now. We will check evaluations and see if we need it
            search_type = "relationships"
            if search_type not in search_settings.graph_settings.limits:
                logger.warning(
                    f"No limit set for graph search type {search_type}, defaulting to global settings limit of {base_limit}"
                )
            async for search_result in self.database_provider.graph_handler.graph_search(  # type: ignore
                input,
                search_type=search_type,
                limit=search_settings.graph_settings.limits.get(
                    search_type, base_limit
                ),
                query_embedding=query_embedding,
                property_names=[
                    # "name",
                    "subject",
                    "predicate",
                    "object",
                    # "name",
                    "description",
                    # "chunk_ids",
                    # "document_ids",
                ],
            ):
                try:
                    # TODO - remove this nasty hack
                    search_result["metadata"] = json.loads(
                        search_result["metadata"]
                    )
                except:
                    pass

                yield GraphSearchResult(
                    content=KGRelationshipResult(
                        # name=search_result["name"],
                        subject=search_result["subject"],
                        predicate=search_result["predicate"],
                        object=search_result["object"],
                        description=search_result["description"],
                    ),
                    result_type=KGSearchResultType.RELATIONSHIP,
                    score=(
                        search_result["similarity_score"]
                        if search_settings.include_scores
                        else None
                    ),
                    # chunk_ids=search_result["chunk_ids"],
                    # document_ids=search_result["document_ids"],
                    metadata=(
                        {
                            "associated_query": message,
                            **(search_result["metadata"] or {}),
                        }
                        if search_settings.include_metadatas
                        else None
                    ),
                )

            # community search
            search_type = "communities"
            async for search_result in self.database_provider.graph_handler.graph_search(  # type: ignore
                message,
                search_type=search_type,
                limit=search_settings.graph_settings.limits.get(
                    search_type, base_limit
                ),
                # embedding_type="embedding",
                query_embedding=query_embedding,
                property_names=[
                    "community_id",
                    "name",
                    "findings",
                    "rating",
                    "rating_explanation",
                    "summary",
                ],
                filters=search_settings.filters,
            ):
                yield GraphSearchResult(
                    content=KGCommunityResult(
                        name=search_result["name"],
                        summary=search_result["summary"],
                        rating=search_result["rating"],
                        rating_explanation=search_result["rating_explanation"],
                        findings=search_result["findings"],
                    ),
                    result_type=KGSearchResultType.COMMUNITY,
                    metadata=(
                        {
                            "associated_query": message,
                            **(search_result["metadata"] or {}),
                        }
                        if search_settings.include_metadatas
                        else None
                    ),
                    score=(
                        search_result["similarity_score"]
                        if search_settings.include_scores
                        else None
                    ),
                )

    async def _run_logic(  # type: ignore
        self,
        input: GeneratorPipe.Input,
        state: AsyncState,
        run_id: UUID,
        search_settings: GraphSearchSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[GraphSearchResult, None]:

        async for result in self.search(input, state, run_id, search_settings):
            yield result
