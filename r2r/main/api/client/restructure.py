class RestructureMethods:
    @staticmethod
    async def enrich_graph(client) -> dict:
        """
        Perform graph enrichment over the entire graph.

        Returns:
            dict: Results of the graph enrichment process.
        """
        return await client._make_request("POST", "kg/enrich_graph")

    @staticmethod
    async def query_graph(client, query: str) -> dict:
        """
        Query the knowledge graph.

        Args:
            query (str): The query to run against the knowledge graph.

        Returns:
            dict: Results of the graph query.
        """
        params = {"query": query}
        return await client._make_request(
            "GET", "kg/query_graph", params=params
        )

    @staticmethod
    async def get_graph_statistics(client) -> dict:
        """
        Get statistics about the knowledge graph.

        Returns:
            dict: Statistics about the knowledge graph.
        """
        return await client._make_request("GET", "kg/graph_statistics")
