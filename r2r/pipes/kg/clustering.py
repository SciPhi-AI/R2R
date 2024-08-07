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
    AsyncState,
    KGProvider,
    PipeType,
    Community,
    CommunityReport,
    AsyncPipe,
    Triple,
    KVLoggingSingleton,
)
from r2r.base.pipes.base_pipe import AsyncPipe

logger = logging.getLogger(__name__)

class KGClusteringPipe(AsyncPipe):
    """
    Clusters entities and triples into communities within the knowledge graph using hierarchical Leiden algorithm.
    """ 

    def __init__(
        self,
        kg_provider: KGProvider,
        cluster_batch_size: int = 100,
        max_cluster_size: int = 10,
        use_lcc: bool = True,
        pipe_logger: Optional[KVLoggingSingleton] = None,
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
        self.cluster_batch_size = cluster_batch_size
        self.max_cluster_size = max_cluster_size
        self.use_lcc = use_lcc

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
            G.add_edge(triple.subject, triple.object, weight=triple.weight, description=triple.description, id = triple.id, predicate=triple.predicate)

        hierarchical_communities = self._compute_leiden_communities(G)

        community_details = {}

        for level, level_communities in hierarchical_communities.items():
            for node, cluster in level_communities.items():
                if f"{level}_{cluster}" not in community_details:
                    community_details[f"{level}_{cluster}"] = Community(
                        id = f"{level}_{cluster}",
                        level=str(level),
                        entity_ids=[],
                        relationship_ids=[],
                        short_id=f"{level}.{cluster}",
                        title=f"Community {level}.{cluster}",
                        attributes= {
                            "name": f"Community {level}.{cluster}",
                            "community_report": None,
                        }
                    )

                community_details[f"{level}_{cluster}"].entity_ids.append(node)
                for neighbor in G.neighbors(node):
                    edge_info = G.get_edge_data(node, neighbor)
                    logger.info(f"Node: {node}")
                    logger.info(f"Neighbor: {neighbor}")
                    logger.info(f"Edge info: {edge_info}")
                    if edge_info and edge_info.get('id'):
                        community_details[f"{level}_{cluster}"].relationship_ids.append(edge_info.get('id'))

        for _, community in community_details.items():
            self.kg_provider.upsert_communities([community])
            yield community
 
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

        triples = self.kg_provider.get_triplets()
        # create a networkx graph

        async for community in self.cluster_kg(triples):
            yield community
