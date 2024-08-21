from typing import Any, Dict, List, Optional, Union

from core.base import Document
from .models import KGEnrichmentSettings, KGEnrichmentResponse

class RestructureMethods:
    @staticmethod
    async def enrich_graph(
        client, KGEnrichmentSettings: KGEnrichmentSettings = KGEnrichmentSettings()
    ) -> KGEnrichmentResponse:
        """
        Perform graph enrichment over the entire graph.

        Returns:
            KGEnrichmentResponse: Results of the graph enrichment process.
        """
        if not isinstance(KGEnrichmentSettings, dict):
            KGEnrichmentSettings = KGEnrichmentSettings.model_dump()

        data = {
            "KGEnrichmentSettings": KGEnrichmentSettings,
        }
        return await client._make_request("POST", "enrich_graph", json=data)
