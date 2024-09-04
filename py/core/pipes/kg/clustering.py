# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""A module for clustering entities and triples into communities using hierarchical Leiden algorithm."""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

import networkx as nx
from tqdm.asyncio import tqdm_asyncio

from core.base import (
    AsyncPipe,
    AsyncState,
    Community,
    CompletionProvider,
    EmbeddingProvider,
    Entity,
    KGEnrichmentSettings,
    KGProvider,
    PipeType,
    PromptProvider,
    RunLoggingSingleton,
    Triple,
    GenerationConfig,
)

logger = logging.getLogger(__name__)


class KGClusteringPipe(AsyncPipe):
    """
    Clusters entities and triples into communities within the knowledge graph using hierarchical Leiden algorithm.
    """

    def __init__(
        self,
        kg_provider: KGProvider,
        llm_provider: CompletionProvider,
        prompt_provider: PromptProvider,
        embedding_provider: EmbeddingProvider,
        pipe_logger: Optional[RunLoggingSingleton] = None,
        type: PipeType = PipeType.OTHER,
        config: Optional[AsyncPipe.PipeConfig] = None,
        *args,
        **kwargs,
    ):
        """
        Initializes the KG clustering pipe with necessary components and configurations.
        """
        super().__init__(
            pipe_logger=pipe_logger,
            type=type,
            config=config or AsyncPipe.PipeConfig(name="kg_cluster_pipe"),
        )
        self.kg_provider = kg_provider
        self.llm_provider = llm_provider
        self.prompt_provider = prompt_provider
        self.embedding_provider = embedding_provider

    def community_summary_prompt(
        self, prompt: str, entities: list[Entity], triples: list[Triple]
    ):
        """
        Preparing the list of entities and triples to be summarized and created into a community summary.
        """
        entities_info = "\n".join(
            [f"{entity.name}, {entity.description}" for entity in entities]
        )

        triples_info = "\n".join(
            [
                f"{triple.subject}, {triple.object}, {triple.predicate}, {triple.description}"
                for triple in triples
            ]
        )

        return prompt.format(entities=entities_info, triples=triples_info)

    async def process_community(
        self, level: int, community_id: str, generation_config: GenerationConfig
    ) -> dict:
        """
        Process a community by summarizing it and creating a summary embedding and storing it to a neo4j database.

        Input:
        - level: The level of the hierarchy.
        - community_id: The ID of the community to process.

        Output:
        - A dictionary with the community id and the title of the community.
        - Output format: {"id": community_id, "title": title}
        """

        input_text = """

            Entities:
            {entities}

            Triples:
            {triples}

        """

        entities, triples = self.kg_provider.get_community_entities_and_triples(
            level=level, community_id=community_id
        )

        if entities == [] or triples == []:
            return None

        description = (
            (
                await self.llm_provider.aget_completion(
                    messages=self.prompt_provider._get_message_payload(
                        task_prompt_name="graphrag_community_reports",
                        task_inputs={
                            "input_text": self.community_summary_prompt(
                                input_text, entities, triples
                            ),
                        },
                    ),
                    generation_config=generation_config,
                )
            )
            .choices[0]
            .message.content
        )

        community = Community(
            id=str(community_id),
            level=str(level),
            summary=description,
            summary_embedding=await self.embedding_provider.async_get_embedding(
                description
            ),
        )

        self.kg_provider.upsert_communities([community])

        try:
            summary = json.loads(community.summary)
        except:
            summary = {"title": ""}

        return {"id": community.id, "title": summary["title"]}

    async def cluster_kg(
        self,
        leiden_params: dict,
        generation_config: GenerationConfig,
    ):
        """
        Clusters the knowledge graph triples into communities using hierarchical Leiden algorithm. Uses neo4j's graph data science library.
        """
        num_communities, num_hierarchies = (
            self.kg_provider.perform_graph_clustering(leiden_params)
        )

        logger.info(f"Clustering completed. Generated {num_communities} communities with {num_hierarchies} hierarchies.")

        for level in range(num_hierarchies):
            for community_id in range(1, num_communities + 1):
                res = await self.process_community(
                    level, community_id, generation_config
                )
                # all values may not be present each level
                if not res:
                    continue
                yield res

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Community, None]:
        """
        Executes the KG clustering pipe: clustering entities and triples into communities.
        """

        leiden_params = input.message.leiden_params
        generation_config = input.message.generation_config

        base_dimension = self.embedding_provider.config.base_dimension
        vector_index_fn = self.kg_provider.create_vector_index
        vector_index_fn("__ENTITY__", "name_embedding", base_dimension)
        vector_index_fn("__ENTITY__", "description_embedding", base_dimension)
        vector_index_fn("__RELATIONSHIP__", "description", base_dimension)
        vector_index_fn("__Community__", "summary_embedding", base_dimension)

        async for community in self.cluster_kg(leiden_params, generation_config):
            yield community
