import json
from typing import Optional, Union

from .models import (
    KGCreationResponse,
    KGCreationSettings,
    KGEnrichmentResponse,
    KGEnrichmentSettings,
)


class KGMethods:

    @staticmethod
    async def create_graph(
        client,
        collection_id: str,
        kg_creation_settings: Optional[Union[dict, KGCreationSettings]] = None,
    ) -> KGCreationResponse:
        """
        Create a graph from the given settings.
        """
        if isinstance(kg_creation_settings, KGCreationSettings):
            kg_creation_settings = kg_creation_settings.model_dump()
        elif kg_creation_settings is None or kg_creation_settings == "{}":
            kg_creation_settings = {}
        elif isinstance(kg_creation_settings, str):
            try:
                kg_creation_settings = json.loads(kg_creation_settings)
            except json.JSONDecodeError:
                raise ValueError(
                    "kg_creation_settings must be a valid JSON string if provided as a string"
                )

        data = {
            "collection_id": collection_id,
            "kg_creation_settings": kg_creation_settings,
        }

        return await client._make_request("POST", "create_graph", json=data)

    @staticmethod
    async def enrich_graph(
        client,
        collection_id: str,
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
        elif isinstance(kg_enrichment_settings, str):
            try:
                kg_enrichment_settings = json.loads(kg_enrichment_settings)
            except json.JSONDecodeError:
                raise ValueError(
                    "kg_enrichment_settings must be a valid JSON string if provided as a string"
                )

        data = {
            "collection_id": collection_id,
            "kg_enrichment_settings": kg_enrichment_settings,
        }

        return await client._make_request("POST", "enrich_graph", json=data)
