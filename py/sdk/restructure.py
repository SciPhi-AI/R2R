from typing import Any, Dict, List, Optional, Union

from core.base import Document
from core.base.api.models import KGEnrichementResponse, KGEnrichmentSettings


class RestructureMethods:
    @staticmethod
    async def enrich_graph(
        client, KGEnrichmentSettings: Union[dict, KGEnrichmentSettings]
    ) -> KGEnrichementResponse:
        """
        Perform graph enrichment over the entire graph.

        Returns:
            KGEnrichementResponse: Results of the graph enrichment process.
        """
        if not isinstance(KGEnrichmentSettings, dict):
            KGEnrichmentSettings = KGEnrichmentSettings.model_dump()

        data = {
            "KGEnrichmentSettings": KGEnrichmentSettings,
        }
        return await client._make_request("POST", "enrich_graph", json=data)
