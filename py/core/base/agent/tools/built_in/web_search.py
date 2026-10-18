from shared.abstractions.tool import Tool


class WebSearchTool(Tool):
    """
    Web search with Parallel MCP, or Serper when configured.
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
        import os

        from core.base.abstractions import (
            AggregateSearchResult,
            WebSearchResult,
        )
        from core.utils.serper import SerperClient

        context = self.context

        provider = os.getenv("R2R_WEB_SEARCH_PROVIDER", "auto").lower()
        if provider == "auto":
            provider = "serper" if os.getenv("SERPER_API_KEY") else "parallel"
        if provider == "parallel":
            from core.utils.parallel_search import search_parallel

            raw_results = await search_parallel(query)
        elif provider == "serper":
            serper_client = SerperClient()
            raw_results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: serper_client.get_raw(query),
            )
        else:
            raise ValueError(
                "R2R_WEB_SEARCH_PROVIDER must be auto, parallel, or serper"
            )

        web_response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: WebSearchResult.from_serper_results(raw_results)
        )

        result = AggregateSearchResult(
            web_search_results=[web_response],
        )

        # Add to results collector if context is provided
        if context and hasattr(context, "search_results_collector"):
            if provider == "parallel":
                # Citation lookup needs each page's ID, rather than the wrapper.
                for page in web_response.organic_results:
                    context.search_results_collector.add_result(
                        page, source_type="web"
                    )
            else:
                context.search_results_collector.add_aggregate_result(result)

        return result
