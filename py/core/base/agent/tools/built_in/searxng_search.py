import logging

from core.utils import (
    generate_id,
)
from shared.abstractions.tool import Tool

logger = logging.getLogger(__name__)


class SearxNGSearchTool(Tool):
    """
    Uses a self-hosted SearxNG instance to perform web searches.
    SearxNG is a free internet metasearch engine which aggregates results
    from various search services and databases.

    Requires SEARXNG_BASE_URL environment variable to be set.
    """

    def __init__(self):
        super().__init__(
            name="searxng_search",
            description=(
                "Use a self-hosted SearxNG search engine to perform an internet-based search and retrieve results. "
                "Useful when you need to search the internet for specific information using a privacy-respecting "
                "metasearch engine. The query should be no more than 400 characters."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search using SearxNG that should be no more than 400 characters.",
                    },
                    "kwargs": {
                        "type": "object",
                        "description": (
                            "Dictionary for additional parameters to pass to SearxNG, such as max_results, categories, and engines."
                            '{"max_results": 10, "categories": ["general"], "engines": ["google", "bing"]}'
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
        Calls SearxNG's search API asynchronously.

        Returns:
            AggregateSearchResult containing web search results.
        """
        import asyncio

        from core.base.abstractions import (
            AggregateSearchResult,
            WebSearchResult,
        )
        from core.utils.searxng import SearxNGClient

        context = self.context

        # Check if query is too long and truncate if necessary
        if len(query) > 400:
            logger.warning(
                f"SearxNG query is {len(query)} characters long, which exceeds the recommended 400 character limit. "
                "Consider breaking into smaller queries for better results."
            )
            query = query[:400]

        try:
            client = SearxNGClient()

            # Extract optional parameters
            max_results = kwargs.get("max_results", 10)
            categories = kwargs.get("categories", None)
            engines = kwargs.get("engines", None)
            language = kwargs.get("language", "en")
            time_range = kwargs.get("time_range", None)

            # Perform search in executor to avoid blocking
            raw_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.search(
                    query=query,
                    max_results=max_results,
                    categories=categories,
                    engines=engines,
                    language=language,
                    time_range=time_range,
                ),
            )

            # Convert to WebSearchResult format
            search_results = [
                WebSearchResult(
                    title=result.title,
                    link=result.url,
                    snippet=result.content,
                    position=index,
                    id=generate_id(result.url),
                    type="searxng_search",
                )
                for index, result in enumerate(raw_response.results)
            ]

            result = AggregateSearchResult(web_search_results=search_results)

            # Add to results collector if context is provided
            if context and hasattr(context, "search_results_collector"):
                context.search_results_collector.add_aggregate_result(result)

            return result
        except ValueError as e:
            logger.warning(f"SearxNG configuration error: {e}")
            return AggregateSearchResult()
        except ImportError as e:
            logger.error(f"Missing dependency: {e}")
            return AggregateSearchResult()
        except Exception as e:
            logger.error(f"Error during SearxNG search: {e}")
            return AggregateSearchResult()
