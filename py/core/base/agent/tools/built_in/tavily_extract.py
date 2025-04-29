from core.base.agent.tools.base import Tool
from typing import Callable

from core.utils import (
    generate_id,
)

import logging

logger = logging.getLogger(__name__)

class TavilyExtractTool:
    """
    Uses the Tavily Search API, to extract content from a specific URL.
    """
    
    def __init__(self):
        self.name = "tavily_extract",
        self.description=(
            "Use Tavily to extract and retrieve the contents of a specific webpage. "
            "This is useful when you want to get clean, structured content from a URL. "
            "Use this when you need to analyze the full content of a specific webpage."
        ),
        self.parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "The absolute URL of the webpage you want to extract content from. "
                        "Example: 'https://www.example.com/article'"
                    ),
                }
            },
            "required": ["url"],
        },
    
    async def execute(self, url: str, context=None, *args, **kwargs):
        """
        Calls Tavily's extract API asynchronously.
        """
        import asyncio
        import os
        from core.base.abstractions import WebPageSearchResult, AggregateSearchResult

        try:
            from tavily import TavilyClient

            # Get API key from environment variables
            api_key = os.environ.get("TAVILY_API_KEY")
            if not api_key:
                logger.warning("TAVILY_API_KEY environment variable not set")
                return AggregateSearchResult(web_search_results=[])

            # Initialize Tavily client
            tavily_client = TavilyClient(api_key=api_key)

            # Perform the URL extraction asynchronously
            extracted_content = await asyncio.get_event_loop().run_in_executor(
                None,  # Uses the default executor
                lambda: tavily_client.extract(url, extract_depth="advanced"),
            )

            web_search_results = []
            for successfulResult in extracted_content.results:
                content = successfulResult.raw_content
                if len(content) > 100_000:
                    content = (
                        f"{content[:100000]}...FURTHER CONTENT TRUNCATED..."
                    )

                web_result = WebPageSearchResult(
                    title=successfulResult.url,
                    link=successfulResult.url,
                    snippet=content,
                    position=0,
                    id=generate_id(successfulResult.url),
                    type="tavily_extract",
                )
                web_search_results.append(web_result)

            result = AggregateSearchResult(web_search_results=web_search_results)

            # Add to results collector if context is provided
            if context and hasattr(context, 'search_results_collector'):
                context.search_results_collector.add_aggregate_result(result)

            return result
        except ImportError:
            logger.error(
                "The 'tavily-python' package is not installed. Please install it with 'pip install tavily-python'"
            )
            # Return empty results in case Tavily is not installed
            return AggregateSearchResult(web_search_results=[])
        except Exception as e:
            logger.error(f"Error during Tavily search: {e}")
            # Return empty results in case of any other error
            return AggregateSearchResult(web_search_results=[])
    
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
