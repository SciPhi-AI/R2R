import json
import logging
import math

from core import GenerationConfig

from ...services import KgService

logger = logging.getLogger(__name__)


def simple_kg_factory(service: KgService):

    def get_input_data_dict(input_data):
        for key, value in input_data.items():
            if key == "kg_creation_settings":
                input_data[key] = json.loads(value)
                input_data[key]["generation_config"] = GenerationConfig(
                    **input_data[key]["generation_config"]
                )
            if key == "kg_enrichment_settings":
                input_data[key] = json.loads(value)
                input_data[key]["generation_config"] = GenerationConfig(
                    **input_data[key]["generation_config"]
                )
        return input_data

    async def create_graph(input_data):

        input_data = get_input_data_dict(input_data)

        document_ids = await service.get_document_ids_for_create_graph(
            collection_id=input_data["collection_id"],
            **input_data["kg_creation_settings"],
        )

        logger.info(
            f"Creating graph for {len(document_ids)} documents with IDs: {document_ids}"
        )

        for _, document_id in enumerate(document_ids):
            # Extract triples from the document
            await service.kg_triples_extraction(
                document_id=document_id,
                **input_data["kg_creation_settings"],
            )
            # Describe the entities in the graph
            await service.kg_entity_description(
                document_id=document_id,
                **input_data["kg_creation_settings"],
            )

    async def enrich_graph(input_data):

        input_data = get_input_data_dict(input_data)

        num_communities = await service.kg_clustering(
            collection_id=input_data["collection_id"],
            **input_data["kg_enrichment_settings"],
        )
        num_communities = num_communities[0]["num_communities"]
        # TODO - Do not hardcode the number of parallel communities,
        # make it a configurable parameter at runtime & add server-side defaults
        parallel_communities = min(100, num_communities)

        total_workflows = math.ceil(num_communities / parallel_communities)
        for i in range(total_workflows):
            input_data_copy = input_data.copy()
            input_data_copy["offset"] = i * parallel_communities
            input_data_copy["limit"] = min(
                parallel_communities,
                num_communities - i * parallel_communities,
            )
            # running i'th workflow out of total_workflows
            logger.info(
                f"Running kg community summary for {i+1}'th workflow out of total {total_workflows} workflows"
            )
            await kg_community_summary(
                input_data=input_data_copy,
            )

        return {"result": "successfully ran kg community summary workflows"}

    async def kg_community_summary(input_data):

        logger.info(
            f"Running kg community summary for offset: {input_data['offset']}, limit: {input_data['limit']}"
        )

        await service.kg_community_summary(
            offset=input_data["offset"],
            limit=input_data["limit"],
            collection_id=input_data["collection_id"],
            **input_data["kg_enrichment_settings"],
        )

    return {
        "create-graph": create_graph,
        "enrich-graph": enrich_graph,
        "kg-community-summary": kg_community_summary,
    }
