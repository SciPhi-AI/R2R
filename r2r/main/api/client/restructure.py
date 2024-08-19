class RestructureMethods:
    @staticmethod
    async def enrich_graph(client) -> dict:
        """
        Perform graph enrichment over the entire graph.

        Returns:
            dict: Results of the graph enrichment process.
        """
        data = {
            "documents": (
                [doc.model_dump() for doc in documents] if documents else None
            )
        }
        return await client._make_request("POST", "enrich_graph", json=data)
