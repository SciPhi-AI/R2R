from typing import Callable

from core.base.agent.tools.base import Tool


class WebSearchTool:
    """
    A web search tool that uses Serper to perform Google searches and returns
    the most relevant results.
    """

    def __init__(self):
        self.name = "web_search"
        self.description = (
            "Search for information on the web - use this tool when the user "
            "query needs LIVE or recent data from the internet."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to search with an external web API.",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, context=None, *args, **kwargs):
        """
        Implementation of web search functionality.
        """
        import asyncio

        from core.base.abstractions import (
            AggregateSearchResult,
            WebSearchResult,
        )
        from core.utils.serper import SerperClient

        serper_client = SerperClient()

        raw_results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: serper_client.get_raw(query),
        )

        web_response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: WebSearchResult.from_serper_results(raw_results)
        )

        result = AggregateSearchResult(
            chunk_search_results=None,
            graph_search_results=None,
            web_search_results=web_response.organic_results,
        )

        # Add to results collector if context is provided
        if context and hasattr(context, "search_results_collector"):
            context.search_results_collector.add_aggregate_result(result)

        return result

    def create_tool(self, format_function: Callable) -> Tool:
        """
        Create and configure a Tool instance with the provided format function.
        """
        return Tool(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            results_function=self.execute,
            llm_format_function=format_function,
        )
