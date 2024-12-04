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

            if type(value) == uuid.UUID:
                continue

            if key == "document_id":
                input_data[key] = uuid.UUID(value)

            if key == "collection_id":
                input_data[key] = uuid.UUID(value)

            # if key == "graph_id":
            #     input_data[key] = uuid.UUID(value)

            if key == "graph_creation_settings":
                input_data[key] = json.loads(value)
                input_data[key]["generation_config"] = GenerationConfig(
                    **input_data[key]["generation_config"]
                )
            if key == "graph_enrichment_settings":
                input_data[key] = json.loads(value)
                input_data[key]["generation_config"] = GenerationConfig(
                    **input_data[key]["generation_config"]
                )
        return input_data

    async def extract_triples(input_data):

        input_data = get_input_data_dict(input_data)

        if input_data.get("document_id"):
            document_ids = [input_data.get("document_id")]
        else:
            documents = []
            collection_id = input_data.get("collection_id")
            batch_size = 100
            offset = 0
            while True:
                # Fetch current batch
                batch = (
                    await service.providers.database.collections_handler.documents_in_collection(
                        collection_id=collection_id,
                        offset=offset,
                        limit=batch_size,
                    )
                )["results"]

                # If no documents returned, we've reached the end
                if not batch:
                    break

                # Add current batch to results
                documents.extend(batch)

                # Update offset for next batch
                offset += batch_size

                # Optional: If batch is smaller than batch_size, we've reached the end
                if len(batch) < batch_size:
                    break

            document_ids = [document.id for document in documents]

        logger.info(
            f"Creating graph for {len(document_ids)} documents with IDs: {document_ids}"
        )

        for _, document_id in enumerate(document_ids):
            # Extract relationships from the document
            try:
                extractions = []
                async for extraction in service.kg_extraction(
                    document_id=document_id,
                    **input_data["graph_creation_settings"],
                ):
                    extractions.append(extraction)
                await service.store_kg_extractions(extractions)

                # Describe the entities in the graph
                await service.kg_entity_description(
                    document_id=document_id,
                    **input_data["graph_creation_settings"],
                )

            except Exception as e:
                logger.error(
                    f"Error in creating graph for document {document_id}: {e}"
                )
                raise e

    async def enrich_graph(input_data):

        input_data = get_input_data_dict(input_data)
        workflow_status = await service.providers.database.get_workflow_status(
            id=input_data.get("collection_id", None),
            status_type="graph_cluster_status",
        )
        if workflow_status == KGEnrichmentStatus.SUCCESS:
            raise R2RException(
                "Communities have already been built for this collection. To build communities again, first submit a POST request to `graphs/{collection_id}/reset` to erase the previously built communities.",
                400,
            )

        try:
            num_communities = await service.kg_clustering(
                collection_id=input_data.get("collection_id", None),
                # graph_id=input_data.get("graph_id", None),
                **input_data["graph_enrichment_settings"],
            )
            num_communities = num_communities[0]["num_communities"]
            # TODO - Do not hardcode the number of parallel communities,
            # make it a configurable parameter at runtime & add server-side defaults

            if num_communities == 0:
                raise R2RException("No communities found", 400)

            parallel_communities = min(100, num_communities[0])

            total_workflows = math.ceil(
                num_communities[0] / parallel_communities
            )
            for i in range(total_workflows):
                input_data_copy = input_data.copy()
                input_data_copy["offset"] = i * parallel_communities
                input_data_copy["limit"] = min(
                    parallel_communities,
                    num_communities[0] - i * parallel_communities,
                )

                logger.info(
                    f"Running kg community summary for workflow {i+1} of {total_workflows}"
                )
                await kg_community_summary(
                    input_data=input_data_copy,
                )

            await service.providers.database.set_workflow_status(
                id=input_data.get("collection_id", None),
                status_type="graph_cluster_status",
                status=KGEnrichmentStatus.SUCCESS,
            )

        except Exception as e:

            await service.providers.database.set_workflow_status(
                id=input_data.get("collection_id", None),
                status_type="graph_cluster_status",
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
            collection_id=input_data.get("collection_id", None),
            # graph_id=input_data.get("graph_id", None),
            **input_data["graph_enrichment_settings"],
        )

    async def entity_deduplication_workflow(input_data):

        # TODO: We should determine how we want to handle the input here and syncronize it across all simple orchestration methods
        if isinstance(input_data["graph_entity_deduplication_settings"], str):
            input_data["graph_entity_deduplication_settings"] = json.loads(
                input_data["graph_entity_deduplication_settings"]
            )

        collection_id = input_data.get("collection_id", None)
        graph_id = input_data.get("graph_id", None)

        number_of_distinct_entities = (
            await service.kg_entity_deduplication(
                collection_id=collection_id,
                graph_id=graph_id,
                **input_data["graph_entity_deduplication_settings"],
            )
        )[0]["num_entities"]

        await service.kg_entity_deduplication_summary(
            collection_id=collection_id,
            offset=0,
            limit=number_of_distinct_entities,
            **input_data["graph_entity_deduplication_settings"],
        )

    return {
        "extract-triples": extract_triples,
        "build-communities": enrich_graph,
        "kg-community-summary": kg_community_summary,
        "entity-deduplication": entity_deduplication_workflow,
    }
