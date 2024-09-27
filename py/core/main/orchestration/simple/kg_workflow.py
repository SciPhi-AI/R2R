import asyncio
import json
import logging
import uuid
import math

from core import GenerationConfig, IngestionStatus, KGCreationSettings
from core.base import R2RDocumentProcessingError
from core.base.abstractions import KGCreationStatus, KGEnrichmentStatus

from ...services import KgService

logger = logging.getLogger(__name__)


def simple_kg_factory(service: KgService):
    
    async def kg_extract(input_data) -> dict:
        await service.kg_extract_and_store(**input_data)
        return await service.kg_node_description(**input_data)

    async def create_graph(input_data):
        document_ids = await service.get_document_ids_for_create_graph(**input_data)
        for cnt, document_id in enumerate(document_ids):
            await service.kg_extract_and_store(document_id=document_id, **input_data)

    async def enrich_graph(input_data):
        num_clusters = await service.kg_clustering(**input_data)
        parallel_communities = min(100, num_clusters)
        workflows = []
        for i, offset in enumerate(
            range(0, num_clusters, parallel_communities)
        ):
            workflows.append(
                kg_community_summary(
                    offset=offset,
                    limit=parallel_communities,
                    **input_data,
                )
            )
        await asyncio.gather(*workflows)
        return {"result": "successfully ran kg community summary workflows"}

    async def kg_community_summary(input_data):
        community_id = input_data["community_id"]
        level = input_data["level"]
        generation_config = GenerationConfig(**input_data["generation_config"])
        max_summary_input_length = input_data["max_summary_input_length"]
        await service.kg_community_summary(
            community_id=community_id,
            level=level,
            max_summary_input_length=max_summary_input_length,
            generation_config=generation_config,
        )


    return {
        "kg-extract": kg_extract,
        "create-graph": create_graph,
        "enrich-graph": enrich_graph,
        "kg-community-summary": kg_community_summary,
    }