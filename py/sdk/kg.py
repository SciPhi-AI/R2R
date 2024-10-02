import json
from typing import Optional, Union
from uuid import UUID

from .models import (
    KGCreationResponse,
    KGCreationSettings,
    KGEnrichmentResponse,
    KGEnrichmentSettings,
    KGRunType,
)


class KGMethods:

    @staticmethod
    async def create_graph(
        client,
        collection_id: Optional[UUID] = None,
        run_type: KGRunType = KGRunType.ESTIMATE,
        kg_creation_settings: Optional[Union[dict, KGCreationSettings]] = None,
    ) -> KGCreationResponse:
        """
        Create a graph from the given settings.
        """
        if isinstance(kg_creation_settings, KGCreationSettings):
            kg_creation_settings = kg_creation_settings.model_dump()
        elif kg_creation_settings is None or kg_creation_settings == "{}":
            kg_creation_settings = {}

        data = {
            "run_type": run_type,
            "kg_creation_settings": json.dumps(kg_creation_settings),
        }

        if collection_id:
            data["collection_id"] = collection_id

        return await client._make_request("POST", "create_graph", json=data)

    @staticmethod
    async def enrich_graph(
        client,
        collection_id: Optional[UUID] = None,
        run_type: KGRunType = KGRunType.ESTIMATE,
        kg_enrichment_settings: Optional[
            Union[dict, KGEnrichmentSettings]
        ] = None,
    ) -> KGEnrichmentResponse:
        """
        Perform graph enrichment over the entire graph.

        Args:
            collection_id (str): The ID of the collection to enrich.
            kg_enrichment_settings (Optional[Union[dict, KGEnrichmentSettings]]): Settings for the graph enrichment process.
        Returns:
            KGEnrichmentResponse: Results of the graph enrichment process.
        """
        if isinstance(kg_enrichment_settings, KGEnrichmentSettings):
            kg_enrichment_settings = kg_enrichment_settings.model_dump()
        elif kg_enrichment_settings is None or kg_enrichment_settings == "{}":
            kg_enrichment_settings = {}

        data = {
            "kg_enrichment_settings": json.dumps(kg_enrichment_settings),
            "run_type": run_type,
        }

        if collection_id:
            data["collection_id"] = collection_id

        return await client._make_request("POST", "enrich_graph", json=data)

    @staticmethod
    async def get_entities(
        client,
        collection_id: str,
        offset: int = 0,
        limit: int = 100,
        entity_ids: Optional[list[str]] = None,
        with_description: bool = False,
    ) -> dict:
        """
        Retrieve entities from the knowledge graph.

        Args:
            collection_id (str): The ID of the collection to retrieve entities from.
            offset (int): The offset for pagination.
            limit (int): The limit for pagination.
            entity_ids (Optional[List[str]]): Optional list of entity IDs to filter by.
            with_description (bool): Whether to include entity descriptions in the response.

        Returns:
            dict: A dictionary containing the retrieved entities and total count.
        """
        params = {
            "collection_id": collection_id,
            "offset": offset,
            "limit": limit,
            "with_description": with_description,
        }
        if entity_ids:
            params["entity_ids"] = ",".join(entity_ids)

        return await client._make_request("GET", "entities", params=params)

    @staticmethod
    async def get_triples(
        client,
        collection_id: str,
        offset: int = 0,
        limit: int = 100,
        triple_ids: Optional[list[str]] = None,
    ) -> dict:
        """
        Retrieve triples from the knowledge graph.

        Args:
            collection_id (str): The ID of the collection to retrieve triples from.
            offset (int): The offset for pagination.
            limit (int): The limit for pagination.
            triple_ids (Optional[List[str]]): Optional list of triple IDs to filter by.

        Returns:
            dict: A dictionary containing the retrieved triples and total count.
        """
        params = {
            "collection_id": collection_id,
            "offset": offset,
            "limit": limit,
        }
        if triple_ids:
            params["triple_ids"] = ",".join(triple_ids)

        return await client._make_request("GET", "triples", params=params)
