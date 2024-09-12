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
        skip_clustering: bool = False,
        force_enrichment: bool = False,
        kg_enrichment_settings: Union[dict, KGEnrichmentSettings] = None,
    ) -> KGEnrichmentResponse:
        """
        Perform graph enrichment over the entire graph.

        Args:
            skip_clustering (bool): Whether to skip leiden clustering on the graph or not.
            force_enrichment (bool): Force Enrichment step even if graph creation is still in progress for some documents.
            kg_enrichment_settings (KGEnrichmentSettings): Settings for the graph enrichment process.
        Returns:
            KGEnrichmentResponse: Results of the graph enrichment process.
        """

        data = {
            "skip_clustering": skip_clustering,
            "force_enrichment": force_enrichment,
            "kg_enrichment_settings": kg_enrichment_settings,
        }
        response = await client._make_request(
            "POST", "enrich_graph", json=data
        )
        return response
