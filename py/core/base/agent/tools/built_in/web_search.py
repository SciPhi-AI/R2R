from shared.abstractions.tool import Tool


class WebSearchTool(Tool):
    """
    A web search tool that uses Serper to perform Google searches and returns
    the most relevant results.
    """

    def __init__(self):
        super().__init__(
            name="web_search",
            description=(
                "Search for information on the web - use this tool when the user "
                "query needs LIVE or recent data from the internet."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search with an external web API.",
                    },
                },
                "required": ["query"],
            },
            results_function=self.execute,
            llm_format_function=None,
        )

    async def execute(self, query: str, *args, **kwargs):
        """
        Implementation of web search functionality.
        """
        import asyncio

        from core.base.abstractions import (
            AggregateSearchResult,
            WebSearchResult,
        )
        from core.utils.serper import SerperClient

        context = self.context

        serper_client = SerperClient()

        raw_results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: serper_client.get_raw(query),
        )

        web_response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: WebSearchResult.from_serper_results(raw_results)
        )

        # FIXME: Need to understand why we would have had this referencing only web_response.organic_results
        result = AggregateSearchResult(
            web_search_results=[web_response],
        )

        # Add to results collector if context is provided
        if context and hasattr(context, "search_results_collector"):
            context.search_results_collector.add_aggregate_result(result)

        return result
