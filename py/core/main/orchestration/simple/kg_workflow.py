import json
import logging
import math
import uuid

from core import GenerationConfig, R2RException
from core.base.abstractions import KGEnrichmentStatus

from ...services import KgService

logger = logging.getLogger()


def simple_kg_factory(service: KgService):

    def get_input_data_dict(input_data):
        for key, value in input_data.items():

            if key == "collection_id":
                input_data[key] = uuid.UUID(value)

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

            try:
                await service.kg_triples_extraction(
                    document_id=document_id,
                    **input_data["kg_creation_settings"],
                )
                # Describe the entities in the graph
                await service.kg_entity_description(
                    document_id=document_id,
                    **input_data["kg_creation_settings"],
                )

            except Exception as e:
                logger.error(
                    f"Error in creating graph for document {document_id}: {e}"
                )

    async def enrich_graph(input_data):

        input_data = get_input_data_dict(input_data)

        try:
            num_communities = await service.kg_clustering(
                collection_id=input_data["collection_id"],
                **input_data["kg_enrichment_settings"],
            )
            num_communities = num_communities[0]["num_communities"]
            # TODO - Do not hardcode the number of parallel communities,
            # make it a configurable parameter at runtime & add server-side defaults

            if num_communities == 0:
                raise R2RException("No communities found", 400)

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

            await service.providers.database.set_workflow_status(
                id=input_data["collection_id"],
                status_type="kg_enrichment_status",
                status=KGEnrichmentStatus.SUCCESS,
            )
            return {
                "result": "successfully ran kg community summary workflows"
            }

        except Exception as e:

            await service.providers.database.set_workflow_status(
                id=input_data["collection_id"],
                status_type="kg_enrichment_status",
                status=KGEnrichmentStatus.FAILED,
            )

            raise e

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

    async def entity_deduplication_workflow(input_data):

        # TODO: We should determine how we want to handle the input here and syncronize it across all simple orchestration methods
        if isinstance(input_data["kg_entity_deduplication_settings"], str):
            input_data["kg_entity_deduplication_settings"] = json.loads(
                input_data["kg_entity_deduplication_settings"]
            )

        collection_id = input_data["collection_id"]

        number_of_distinct_entities = (
            await service.kg_entity_deduplication(
                collection_id=collection_id,
                **input_data["kg_entity_deduplication_settings"],
            )
        )[0]["num_entities"]

        await service.kg_entity_deduplication_summary(
            collection_id=collection_id,
            offset=0,
            limit=number_of_distinct_entities,
            **input_data["kg_entity_deduplication_settings"],
        )

    return {
        "create-graph": create_graph,
        "enrich-graph": enrich_graph,
        "kg-community-summary": kg_community_summary,
        "entity-deduplication": entity_deduplication_workflow,
    }
