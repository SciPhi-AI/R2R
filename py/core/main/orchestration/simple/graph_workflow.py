import json
import logging
import math
import uuid

from core import GenerationConfig, R2RException
from core.base.abstractions import (
    GraphConstructionStatus,
    GraphExtractionStatus,
)

from ...services import GraphService

logger = logging.getLogger()


def simple_graph_search_results_factory(service: GraphService):
    def get_input_data_dict(input_data):
        for key, value in input_data.items():
            if type(value) == uuid.UUID:
                continue

            if key == "document_id":
                input_data[key] = uuid.UUID(value)

            if key == "collection_id":
                input_data[key] = uuid.UUID(value)
            if key == "graph_creation_settings":
                input_data[key] = (
                    json.loads(value) if not isinstance(value, dict) else value
                )
                input_data[key]["generation_config"] = (
                    GenerationConfig(**input_data[key]["generation_config"])
                    if input_data[key]["generation_config"]
                    else GenerationConfig()
                )
            if key == "graph_enrichment_settings":
                input_data[key] = (
                    json.loads(value) if not isinstance(value, dict) else value
                )
                input_data[key]["generation_config"] = (
                    GenerationConfig(**input_data[key]["generation_config"])
                    if input_data[key]["generation_config"]
                    else GenerationConfig()
                )
        return input_data

    async def graph_extraction(input_data):
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

            await service.providers.database.documents_handler.set_workflow_status(
                id=document_id,
                status_type="extraction_status",
                status=GraphExtractionStatus.PROCESSING,
            )

            # Extract relationships from the document
            try:
                extractions = []
                async for (
                    extraction
                ) in service.graph_search_results_extraction(
                    document_id=document_id,
                    **input_data["graph_creation_settings"],
                ):
                    extractions.append(extraction)
                await service.store_graph_search_results_extractions(
                    extractions
                )

                # Describe the entities in the graph
                await service.graph_search_results_entity_description(
                    document_id=document_id,
                    **input_data["graph_creation_settings"],
                )

                if (
                    service.providers.database.config.graph_creation_settings.automatic_deduplication
                ):
                    logger.warning(
                        "Automatic deduplication is not yet implemented for `simple` workflows."
                    )

            except Exception as e:
                logger.error(
                    f"Error in creating graph for document {document_id}: {e}"
                )
                raise e

    async def graph_clustering(input_data):
        input_data = get_input_data_dict(input_data)
        workflow_status = await service.providers.database.documents_handler.get_workflow_status(
            id=input_data.get("collection_id", None),
            status_type="graph_cluster_status",
        )
        if workflow_status == GraphConstructionStatus.SUCCESS:
            raise R2RException(
                "Communities have already been built for this collection. To build communities again, first submit a POST request to `graphs/{collection_id}/reset` to erase the previously built communities.",
                400,
            )

        try:
            num_communities = await service.graph_search_results_clustering(
                collection_id=input_data.get("collection_id", None),
                # graph_id=input_data.get("graph_id", None),
                **input_data["graph_enrichment_settings"],
            )
            num_communities = num_communities["num_communities"][0]
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

                logger.info(
                    f"Running graph_search_results community summary for workflow {i+1} of {total_workflows}"
                )
                await graph_community_summarization(
                    input_data=input_data_copy,
                )

            await service.providers.database.documents_handler.set_workflow_status(
                id=input_data.get("collection_id", None),
                status_type="graph_cluster_status",
                status=GraphConstructionStatus.SUCCESS,
            )

        except Exception as e:
            await service.providers.database.documents_handler.set_workflow_status(
                id=input_data.get("collection_id", None),
                status_type="graph_cluster_status",
                status=GraphConstructionStatus.FAILED,
            )

            raise e

    async def graph_community_summarization(input_data):
        logger.info(
            f"Running graph_search_results community summary for offset: {input_data['offset']}, limit: {input_data['limit']}"
        )

        await service.graph_community_summarization(
            offset=input_data["offset"],
            limit=input_data["limit"],
            collection_id=input_data.get("collection_id", None),
            # graph_id=input_data.get("graph_id", None),
            **input_data["graph_enrichment_settings"],
        )

    async def graph_deduplication(input_data):
        input_data = get_input_data_dict(input_data)
        await service.graph_deduplication(
            document_id=input_data.get("document_id", None),
        )

    return {
        "graph-extraction": graph_extraction,
        "graph-clustering": graph_clustering,
        "graph-community-summarization": graph_community_summarization,
        "graph-deduplication": graph_deduplication,
    }
