from typing import Any, Dict, List, Optional

from r2r.base import Document


class RestructureMethods:
    @staticmethod
    async def enrich_graph(
        client, documents: Optional[List[Document]] = None
    ) -> Dict[str, Any]:
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
        return await client._make_request("POST", "kg/enrich_graph", json=data)

    @staticmethod
    async def query_graph(client, query: str) -> Dict[str, Any]:
        """
        Query the knowledge graph.

        Args:
            query (str): The query to run against the knowledge graph.

        Returns:
            Dict[str, Any]: Results of the graph query.
        """
        params = {"query": query}
        return await client._make_request(
            "GET", "kg/query_graph", params=params
        )

    @staticmethod
    async def get_graph_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge graph.

        Returns:
            Dict[str, Any]: Statistics about the knowledge graph.
        """
        return await client._make_request("GET", "kg/graph_statistics")
