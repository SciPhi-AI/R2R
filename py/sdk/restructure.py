from typing import Union

from .models import KGEnrichmentResponse, KGEnrichmentSettings


class RestructureMethods:
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
        return await client._make_request("POST", "enrich_graph", json=data)
