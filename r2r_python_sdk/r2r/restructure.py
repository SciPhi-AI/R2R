class RestructureMethods:
    @staticmethod
    async def enrich_graph(client) -> dict:
        """
        Perform graph enrichment over the entire graph.

        Returns:
            dict: Results of the graph enrichment process.
        """
        return await client._make_request("POST", "enrich_graph")
