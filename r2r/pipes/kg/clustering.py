# Copyright (c) 2024 Microsoft Corporation.
# Licensed under the MIT License

"""A module for clustering entities and triples into communities using hierarchical Leiden algorithm."""

import asyncio
import logging
import uuid
from typing import Any, AsyncGenerator, Optional

import networkx as nx
from graspologic.partition import hierarchical_leiden

from r2r.base import (
    AsyncPipe,
    AsyncState,
    Community,
    CompletionProvider,
    EmbeddingProvider,
    GenerationConfig,
    KGProvider,
    PipeType,
    PromptProvider,
    RunLoggingSingleton,
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
        cluster_batch_size: int = 100,
        max_cluster_size: int = 10,
        use_lcc: bool = True,
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
        self.cluster_batch_size = cluster_batch_size
        self.max_cluster_size = max_cluster_size
        self.use_lcc = use_lcc
        self.prompt_provider = prompt_provider
        self.embedding_provider = embedding_provider

    def _compute_leiden_communities(
        self,
        graph: nx.Graph,
        seed: int = 0xDEADBEEF,
    ) -> dict[int, dict[str, int]]:
        """Compute Leiden communities."""
        community_mapping = hierarchical_leiden(
            graph, max_cluster_size=self.max_cluster_size, random_seed=seed
        )
        results: dict[int, dict[str, int]] = {}
        for partition in community_mapping:
            results[partition.level] = results.get(partition.level, {})
            results[partition.level][partition.node] = partition.cluster

        return results

    async def cluster_kg(self, triples: list[Triple]) -> list[Community]:
        """
        Clusters the knowledge graph triples into communities using hierarchical Leiden algorithm.
        """

        #         for record in data:
        #     source = EntityNode(
        #         name=record["source_id"],
        #         label=record["source_type"],
        #         properties=remove_empty_values(record["source_properties"]),
        #     )
        #     target = EntityNode(
        #         name=record["target_id"],
        #         label=record["target_type"],
        #         properties=remove_empty_values(record["target_properties"]),
        #     )
        #     rel = Relation(
        #         source_id=record["source_id"],
        #         target_id=record["target_id"],
        #         label=record["type"],
        #     )
        #     triples.append([source, rel, target])
        # return triples

        G = nx.Graph()
        for triple in triples:
            G.add_edge(
                triple.subject,
                triple.object,
                weight=triple.weight,
                description=triple.description,
                predicate=triple.predicate,
                id=f"{triple.subject}->{triple.predicate}->{triple.object}",
            )

        hierarchical_communities = self._compute_leiden_communities(G)

        community_details = {}

        for level, level_communities in hierarchical_communities.items():
            for node, cluster in level_communities.items():
                if f"{level}_{cluster}" not in community_details:
                    community_details[f"{level}_{cluster}"] = Community(
                        id=f"{level}_{cluster}",
                        level=str(level),
                        entity_ids=[],
                        relationship_ids=[],
                        short_id=f"{level}.{cluster}",
                        title=f"Community {level}.{cluster}",
                        attributes={
                            "name": f"Community {level}.{cluster}",
                            "community_report": None,
                        },
                    )

                community_details[f"{level}_{cluster}"].entity_ids.append(node)
                for neighbor in G.neighbors(node):
                    edge_info = G.get_edge_data(node, neighbor)
                    logger.info(f"Node: {node}")
                    logger.info(f"Neighbor: {neighbor}")
                    logger.info(f"Edge info: {edge_info}")
                    if edge_info and edge_info.get("id"):
                        community_details[
                            f"{level}_{cluster}"
                        ].relationship_ids.append(edge_info.get("id"))

        async def async_iterate_dict(dictionary):
            for key, value in dictionary.items():
                yield key, value

        async def process_community(community_key, community):
            input_text = """

                Entities:
                {entities}

                Relationships:
                {relationships}

            """

            entities_info = self.kg_provider.get_entities(community.entity_ids)
            entities_info = "\n".join(
                [
                    f"{entity.name}, {entity.description}"
                    for entity in entities_info
                ]
            )

            relationships_info = self.kg_provider.get_triples(
                community.relationship_ids
            )
            relationships_info = "\n".join(
                [
                    f"{relationship.subject}, {relationship.object}, {relationship.predicate}, {relationship.description}"
                    for relationship in relationships_info
                ]
            )

            input_text = input_text.format(
                entities=entities_info, relationships=relationships_info
            )

            description = await self.llm_provider.aget_completion(
                messages=self.prompt_provider._get_message_payload(
                    task_prompt_name="graphrag_community_reports",
                    task_inputs={
                        "input_text": input_text,
                    },
                ),
                generation_config=GenerationConfig(
                    model="gpt-4o-mini",
                ),
            )

            description = description.choices[0].message.content

            logger.info(f"Community description: {description}")

            community.summary = description

            summary_embedding = (
                await self.embedding_provider.async_get_embedding(
                    community.summary
                )
            )
            community.summary_embedding = summary_embedding
            self.kg_provider.upsert_communities([community])
            return community

        tasks = []
        async for community_key, community in async_iterate_dict(
            community_details
        ):
            tasks.append(
                asyncio.create_task(
                    process_community(community_key, community)
                )
            )

        for completed_task in asyncio.as_completed(tasks):
            yield await completed_task

    async def _process_batch(self, triples: list[Triple]) -> list[Community]:
        """
        Processes a batch of triples and returns the resulting communities.
        """
        return await self.cluster_kg(triples)

    async def _run_logic(
        self,
        input: AsyncPipe.Input,
        state: AsyncState,
        run_id: uuid.UUID,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[Community, None]:
        """
        Executes the KG clustering pipe: clustering entities and triples into communities.
        """
        # batch_tasks = []
        # triple_batch = []

        # async for triple in input.message:
        #     triple_batch.append(triple)
        #     if len(triple_batch) >= self.cluster_batch_size:
        #         batch_tasks.append(self._process_batch(triple_batch.copy()))
        #         triple_batch.clear()

        # if triple_batch:  # Process any remaining triples
        #     batch_tasks.append(self._process_batch(triple_batch))

        # for task in asyncio.as_completed(batch_tasks):
        #     communities = await task
        #     for community in communities:
        #         yield community

        # store all inputs

        all_nodes = []
        async for node in input.message:
            all_nodes.append(node)

        triples = self.kg_provider.get_triples()
        # create a networkx graph

        async for community in self.cluster_kg(triples):
            yield community

        # then finally create vector indexes for communities
        self.kg_provider.create_vector_index("__ENTITY__", "name_embedding")
        self.kg_provider.create_vector_index(
            "__ENTITY__", "description_embedding"
        )

        self.kg_provider.create_vector_index("__RELATIONSHIP__", "description")

        self.kg_provider.create_vector_index(
            "__Community__", "summary_embedding"
        )
