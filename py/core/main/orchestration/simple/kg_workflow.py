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

    def get_input_data_dict(input_data):
        for key, value in input_data.items():
            if key == "kg_creation_settings":
                input_data[key] = json.loads(value)
                input_data[key]['generation_config'] = GenerationConfig(**input_data[key]['generation_config'])
        return input_data

    async def create_graph(input_data):

        input_data = get_input_data_dict(input_data)

        document_ids = await service.get_document_ids_for_create_graph(
            collection_id=input_data["collection_id"],
            **input_data["kg_creation_settings"],
        )
        for cnt, document_id in enumerate(document_ids):
            await service.kg_extraction(
                document_id=document_id,
                **input_data["kg_creation_settings"],
            )

    async def enrich_graph(input_data):

        input_data = get_input_data_dict(input_data)

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
        "create-graph": create_graph,
        "enrich-graph": enrich_graph,
        "kg-community-summary": kg_community_summary,
    }
