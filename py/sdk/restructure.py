from .models import KGEnrichmentResponse, KGEnrichmentSettings


class RestructureMethods:
    @staticmethod
    async def enrich_graph(
        client,
        KGEnrichmentSettings: KGEnrichmentSettings = KGEnrichmentSettings(),
    ) -> KGEnrichmentResponse:
        """
        Perform graph enrichment over the entire graph.

        Args:
            KGEnrichmentSettings (KGEnrichmentSettings): Settings for the graph enrichment process.

        Returns:
            KGEnrichmentResponse: Results of the graph enrichment process.
        """
        if not isinstance(KGEnrichmentSettings, dict):
            KGEnrichmentSettings = KGEnrichmentSettings.model_dump()

        data = {
            "KGEnrichmentSettings": KGEnrichmentSettings,
        }
        return await client._make_request("POST", "enrich_graph", json=data)
