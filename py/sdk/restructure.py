from typing import Union

from .models import (
    KGCreationResponse,
    KGCreationSettings,
    KGEnrichmentResponse,
    KGEnrichmentSettings,
)


class RestructureMethods:

    @staticmethod
    async def create_graph(
        client,
        document_ids: list[str] = None,
        kg_creation_settings: Union[dict, KGCreationSettings] = None,
    ) -> KGCreationResponse:
        """
        Create a graph from the given settings.
        """
        if kg_creation_settings is not None and not isinstance(
            kg_creation_settings, dict
        ):
            kg_creation_settings = kg_creation_settings.model_dump()

        data = {
            "document_ids": document_ids,
            "kg_creation_settings": kg_creation_settings,
        }
        response = await client._make_request(
            "POST", "create_graph", json=data
        )
        return response

    @staticmethod
    async def enrich_graph(
        client,
        kg_enrichment_settings: Union[dict, KGEnrichmentSettings] = None,
    ) -> KGEnrichmentResponse:
        """
        Perform graph enrichment over the entire graph.

        Args:
            kg_enrichment_settings (KGEnrichmentSettings): Settings for the graph enrichment process.

        Returns:
            KGEnrichmentResponse: Results of the graph enrichment process.
        """
        if kg_enrichment_settings is not None and not isinstance(
            kg_enrichment_settings, dict
        ):
            kg_enrichment_settings = kg_enrichment_settings.model_dump()

        data = {
            "kg_enrichment_settings": kg_enrichment_settings,
        }
        response = await client._make_request(
            "POST", "enrich_graph", json=data
        )
        return response
