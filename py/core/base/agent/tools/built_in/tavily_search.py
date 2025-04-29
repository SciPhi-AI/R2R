import logging

from core.utils import (
    generate_id,
)
from shared.abstractions.tool import Tool

logger = logging.getLogger(__name__)


class TavilySearchTool(Tool):
    """
    Uses the Tavily Search API, a specialized search engine designed for
    Large Language Models (LLMs) and AI agents.
    """

    def __init__(self):
        super().__init__(
            name="tavily_search",
            description=(
                "Use the Tavily search engine to perform an internet-based search and retrieve results. Useful when you need "
                "to search the internet for specific information.  The query should be no more than 400 characters."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search using Tavily that should be no more than 400 characters.",
                    },
                    "kwargs": {
                        "type": "object",
                        "description": (
                            "Dictionary for additional parameters to pass to Tavily, such as max_results, include_domains and exclude_domains."
                            '{"max_results": 10, "include_domains": ["example.com"], "exclude_domains": ["example2.com"]}'
                        ),
                    },
                },
                "required": ["query"],
            },
            results_function=self.execute,
            llm_format_function=None,
        )

    async def execute(self, query: str, *args, **kwargs):
        """
        Calls Tavily's search API asynchronously.
        """
        import asyncio
        import os

        from core.base.abstractions import (
            AggregateSearchResult,
            WebSearchResult,
        )

        context = self.context

        # Check if query is too long and truncate if necessary. Tavily recommends under 400 chars.
        if len(query) > 400:
            logger.warning(
                f"Tavily query is {len(query)} characters long, which exceeds the recommended 400 character limit. Consider breaking into smaller queries for better results."
            )
            query = query[:400]

        try:
            from tavily import TavilyClient

            # Get API key from environment variables
            api_key = os.environ.get("TAVILY_API_KEY")
            if not api_key:
                logger.warning("TAVILY_API_KEY environment variable not set")
                return AggregateSearchResult()

            # Initialize Tavily client
            tavily_client = TavilyClient(api_key=api_key)

            # Perform the search asynchronously
            raw_results = await asyncio.get_event_loop().run_in_executor(
                None,  # Uses the default executor
                lambda: tavily_client.search(
                    query=query,
                    search_depth="advanced",
                    include_raw_content=False,
                    include_domains=kwargs.get("include_domains", []),
                    exclude_domains=kwargs.get("exclude_domains", []),
                    max_results=kwargs.get("max_results", 10),
                ),
            )

            # Extract the results from the response
            results = raw_results.get("results", [])

            # Process the raw results into a format compatible with AggregateSearchResult
            search_results = [
                WebSearchResult(  # type: ignore
                    title=result.get("title", "Untitled"),
                    link=result.get("url", ""),
                    snippet=result.get("content", ""),
                    position=index,
                    id=generate_id(result.get("url", "")),
                    type="tavily_search",
                )
                for index, result in enumerate(results)
            ]

            result = AggregateSearchResult(web_search_results=search_results)

            # Add to results collector if context is provided
            if context and hasattr(context, "search_results_collector"):
                context.search_results_collector.add_aggregate_result(result)

            return result
        except ImportError:
            logger.error(
                "The 'tavily-python' package is not installed. Please install it with 'pip install tavily-python'"
            )
            # Return empty results in case Tavily is not installed
            return AggregateSearchResult()
        except Exception as e:
            logger.error(f"Error during Tavily search: {e}")
            # Return empty results in case of any other error
            return AggregateSearchResult()
