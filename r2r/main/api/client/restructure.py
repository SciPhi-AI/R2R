from typing import Any, Dict, List, Optional

from r2r.base import Document
from r2r.base.api.models import KGEnrichementResponse


class RestructureMethods:
    @staticmethod
    async def enrich_graph(
        client, documents: Optional[List[Document]] = None
    ) -> KGEnrichementResponse:
        """
        Perform graph enrichment on the given documents.

        Args:
            documents (Optional[List[Document]]): List of documents to enrich. If None, enriches the entire graph.

        Returns:
            Dict[str, Any]: Results of the graph enrichment process.
        """
        data = {
            "documents": (
                [doc.model_dump() for doc in documents] if documents else None
            )
        }
        return await client._make_request("POST", "enrich_graph", json=data)