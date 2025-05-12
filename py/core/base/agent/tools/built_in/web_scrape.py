import logging

from core.utils import (
    generate_id,
)
from shared.abstractions.tool import Tool

logger = logging.getLogger(__name__)


class WebScrapeTool(Tool):
    """
    A web scraping tool that uses Firecrawl to to scrape a single URL and return
    its contents in an LLM-friendly format (e.g. markdown).
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
                    }
                },
                "required": ["url"],
            },
            results_function=self.execute,
            llm_format_function=None,
        )

    async def execute(self, url: str, *args, **kwargs):
        """
        Performs the Firecrawl scrape asynchronously.
        """
        import asyncio

        from firecrawl import FirecrawlApp

        from core.base.abstractions import (
            AggregateSearchResult,
            WebPageSearchResult,
        )

        context = self.context
        app = FirecrawlApp()
        logger.debug(f"[Firecrawl] Scraping URL={url}")

        response = await asyncio.get_event_loop().run_in_executor(
            None,  # Uses the default executor
            lambda: app.scrape_url(
                url=url,
                formats=["markdown"],
            ),
        )

        markdown_text = response.markdown or ""
        metadata = response.metadata or {}
        page_title = metadata.get("title", "Untitled page")

        if len(markdown_text) > 100_000:
            markdown_text = (
                f"{markdown_text[:100000]}...FURTHER CONTENT TRUNCATED..."
            )

        # Create a single WebPageSearchResult HACK - TODO FIX
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
