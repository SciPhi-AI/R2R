import logging

from core.utils import (
    generate_id,
)
from shared.abstractions.tool import Tool

logger = logging.getLogger(__name__)


class WebScrapeTool(Tool):
    """
    A web scraping tool that uses Firecrawl to scrape a single URL and return
    its contents in an LLM-friendly format (e.g. markdown).

    Supports both cloud Firecrawl and self-hosted instances.
    Set FIRECRAWL_API_URL and FIRECRAWL_API_KEY environment variables
    to use a self-hosted Firecrawl instance.
    """

    def __init__(self):
        super().__init__(
            name="web_scrape",
            description=(
                "Use Firecrawl to scrape a single webpage and retrieve its contents "
                "as clean markdown. Useful when you need the entire body of a page, "
                "not just a quick snippet or standard web search result."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "The absolute URL of the webpage you want to scrape. "
                            "Example: 'https://docs.firecrawl.dev/getting-started'"
                        ),
                    },
                    "kwargs": {
                        "type": "object",
                        "description": (
                            "Dictionary for additional parameters to pass to Firecrawl, "
                            "such as formats, only_main_content, and headers."
                            '{"formats": ["markdown", "html"], "only_main_content": true}'
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
        Performs the Firecrawl scrape asynchronously.

        Supports both cloud Firecrawl and self-hosted instances.
        Set FIRECRAWL_API_URL and FIRECRAWL_API_KEY environment variables
        to use a self-hosted Firecrawl instance.

        Returns:
            AggregateSearchResult containing scraped web page content.
        """
        import asyncio

        from core.base.abstractions import (
            AggregateSearchResult,
            WebPageSearchResult,
        )
        from core.utils.firecrawl import FirecrawlClient

        context = self.context

        try:
            # Create client (reads from env vars automatically)
            client = FirecrawlClient()

            # Extract optional parameters
            formats = kwargs.get("formats", ["markdown"])
            only_main_content = kwargs.get("only_main_content", True)
            include_tags = kwargs.get("include_tags", None)
            exclude_tags = kwargs.get("exclude_tags", None)
            headers = kwargs.get("headers", None)
            wait_for = kwargs.get("wait_for", 0)

            # Perform scrape in executor to avoid blocking
            scrape_result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.scrape_url(
                    url=url,
                    formats=formats,
                    only_main_content=only_main_content,
                    include_tags=include_tags,
                    exclude_tags=exclude_tags,
                    headers=headers,
                    wait_for=wait_for,
                ),
            )

            if not scrape_result.success:
                logger.error(
                    f"Firecrawl scrape failed for {url}: {scrape_result.error}"
                )
                return AggregateSearchResult()

            markdown_text = scrape_result.markdown or ""
            page_title = (
                scrape_result.metadata.title if scrape_result.metadata else ""
            ) or "Untitled page"

            # Truncate if too long
            if len(markdown_text) > 100_000:
                markdown_text = (
                    f"{markdown_text[:100000]}...FURTHER CONTENT TRUNCATED..."
                )

            web_result = WebPageSearchResult(
                title=page_title,
                link=url,
                snippet=markdown_text,
                position=0,
                id=generate_id(markdown_text),
                type="firecrawl",
            )

            result = AggregateSearchResult(web_page_search_results=[web_result])

            # Add to results collector if context is provided
            if context and hasattr(context, "search_results_collector"):
                context.search_results_collector.add_aggregate_result(result)

            return result
        except ValueError as e:
            logger.warning(f"Firecrawl configuration error: {e}")
            return AggregateSearchResult()
        except ImportError as e:
            logger.error(f"Missing dependency: {e}")
            return AggregateSearchResult()
        except Exception as e:
            logger.error(f"Error during Firecrawl scrape: {e}")
            return AggregateSearchResult()
