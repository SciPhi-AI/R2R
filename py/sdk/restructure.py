from typing import Any, Dict, List, Optional

from core.base import Document
from core.base.api.models import KGEnrichementResponse


class RestructureMethods:
    @staticmethod
    async def enrich_graph(client) -> KGEnrichementResponse:
        """
        Perform graph enrichment over the entire graph.

        Returns:
            KGEnrichementResponse: Results of the graph enrichment process.
        """
        return await client._make_request("POST", "enrich_graph")
