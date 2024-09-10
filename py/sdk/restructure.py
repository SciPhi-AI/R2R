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
        perform_clustering: bool = True,
        kg_enrichment_settings: Union[dict, KGEnrichmentSettings] = None,
    ) -> KGEnrichmentResponse:
        """
        Perform graph enrichment over the entire graph.

        Args:
            perform_clustering (bool): Whether to perform leiden clustering on the graph or not.
            kg_enrichment_settings (KGEnrichmentSettings): Settings for the graph enrichment process.
        Returns:
            KGEnrichmentResponse: Results of the graph enrichment process.
        """

        data = {
            "perform_clustering": perform_clustering,
            "kg_enrichment_settings": kg_enrichment_settings,
        }
        response = await client._make_request(
            "POST", "enrich_graph", json=data
        )
        return response
