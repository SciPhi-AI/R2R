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
    KGEnrichmentSettings,
    KGProvider,
    PipeType,
    PromptProvider,
    RunLoggingSingleton,
    Entity,
    Triple,
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

    def community_summary_prompt(self, prompt: str, entities: list[Entity], triples: list[Triple]):
        """
            Preparing the list of entities and triples to be summarized and created into a community summary.
        """
        entities_info = "\n".join(
            [
                f"{entity.name}, {entity.description}"
                for entity in entities
            ]
        )

        triples_info = "\n".join(
            [
                f"{triple.subject}, {triple.object}, {triple.predicate}, {triple.description}"
                for triple in triples
            ]
        )

        return prompt.format(entities=entities_info, triples=triples_info)

    async def process_community(self, community_id: str, settings: KGEnrichmentSettings) -> dict:
        """
            Process a community by summarizing it and creating a summary embedding.

            Input:
            - community_id: The ID of the community to process. This is a string that is constructed by the neo4j leiden clustering algorithm.

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

        entities, triples = self.kg_provider.get_entities_and_triples(community_id = community_id)

        description = await self.llm_provider.aget_completion(
            messages=self.prompt_provider._get_message_payload(
                task_prompt_name="graphrag_community_reports",
                task_inputs={
                    "input_text": self.community_summary_prompt(input_text, entities, triples),
                },
            ),
            generation_config=settings.generation_config_enrichment,
        ).choices[0].message.content

        community = Community(
            id=community_id,
            summary=description,
            summary_embedding=await self.embedding_provider.async_get_embedding(description),
        )

        self.kg_provider.upsert_communities([community])
        
        try:
            summary = json.loads(community.summary)
        except:
            summary = {"title": ""}

        return {"id": community.id, "title": summary["title"]}


    async def get_communities(self, filters: dict, settings: KGEnrichmentSettings = KGEnrichmentSettings()):
        """
        Clusters the knowledge graph triples into communities using hierarchical Leiden algorithm. Uses neo4j's graph data science library.
        """
        num_communities, num_hierarchies = self.kg_provider.perform_graph_clustering(settings.leiden_params)
        
        for i in range(num_communities):
            for j in range(num_hierarchies):
                community_id = f"{i}_{j}"
                yield await self.process_community(community_id, settings)

    
    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: UUID,
        kg_enrichment_settings: KGEnrichmentSettings,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Community, None]:
        """
        Executes the KG clustering pipe: clustering entities and triples into communities.
        """

        base_dimension = self.embedding_provider.config.base_dimension
        vector_index_fn = self.kg_provider.create_vector_index
        vector_index_fn("__ENTITY__", "name_embedding", base_dimension)
        vector_index_fn("__ENTITY__", "description_embedding", base_dimension)
        vector_index_fn("__RELATIONSHIP__", "description", base_dimension)
        vector_index_fn("__Community__", "summary_embedding", base_dimension)

        all_nodes = []
        async for node in input.message:
            all_nodes.append(node)

        async for community in self.cluster_kg(
            {}, kg_enrichment_settings
        ):
            community = await self.process_community(community)
            yield community
