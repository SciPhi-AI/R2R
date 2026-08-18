import logging

from core.utils import (
    generate_id,
)
from shared.abstractions.tool import Tool

logger = logging.getLogger(__name__)


class SearxNGExtractTool(Tool):
    """
    Uses a self-hosted SearxNG instance to extract content from URLs.
    This tool fetches and extracts the main content from a webpage using
    SearxNG's built-in content extraction capabilities.

    Requires SEARXNG_BASE_URL environment variable to be set.
    """

    def __init__(self):
        super().__init__(
            name="searxng_extract",
            description=(
                "Use SearxNG to extract and retrieve the contents of a specific webpage. "
                "This is useful when you want to get clean, structured content from a URL. "
                "Use this when you need to analyze the full content of a specific webpage."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "The absolute URL of the webpage you want to extract content from. "
                            "Example: 'https://www.example.com/article'"
                        ),
                    },
                    "kwargs": {
                        "type": "object",
                        "description": (
                            "Dictionary for additional parameters, such as engines to use for extraction."
                            '{"engines": ["google", "bing"]}'
                        ),
                    },
                },
                "required": ["url"],
            },
            results_function=self.execute,
            llm_format_function=None,
        )

    async def execute(self, url: str, *args, **kwargs):
        """
        Extracts content from a URL using SearxNG.

        Returns:
            AggregateSearchResult containing extracted web page content.
        """
        import asyncio

        from core.base.abstractions import (
            AggregateSearchResult,
            WebPageSearchResult,
        )
        from core.utils.searxng import SearxNGClient

        context = self.context

        try:
            client = SearxNGClient()
            engines = kwargs.get("engines", None)

            # Extract content in executor
            content = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.extract_content(url=url, engines=engines),
            )

            if not content:
                logger.warning(f"No content extracted from {url}")
                return AggregateSearchResult()

            # Truncate if too long
            if len(content) > 100_000:
                content = f"{content[:100000]}...FURTHER CONTENT TRUNCATED..."

            web_result = WebPageSearchResult(
                title=url,
                link=url,
                snippet=content,
                position=0,
                id=generate_id(content),
                type="searxng_extract",
            )

            result = AggregateSearchResult(
                web_page_search_results=[web_result]
            )

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
            logger.error(f"Error during SearxNG extraction: {e}")
            return AggregateSearchResult()
