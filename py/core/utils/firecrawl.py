"""Firecrawl client for web scraping and content extraction.

Supports both the cloud Firecrawl API and self-hosted instances.

Usage:
    # Cloud Firecrawl
    export FIRECRAWL_API_KEY=your-api-key
    client = FirecrawlClient()

    # Self-hosted Firecrawl
    export FIRECRAWL_API_URL=http://localhost:3002
    export FIRECRAWL_API_KEY=your-api-key
    client = FirecrawlClient()

    # Or pass directly
    client = FirecrawlClient(
        api_url="http://localhost:3002",
        api_key="your-api-key"
    )
    result = client.scrape_url("https://example.com")
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FirecrawlMetadata:
    """Metadata from a Firecrawl scrape."""

    title: str = ""
    description: str = ""
    language: str = ""
    source_url: str = ""
    raw_content: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "FirecrawlMetadata":
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            language=data.get("language", ""),
            source_url=data.get("sourceURL", ""),
            raw_content=data.get("rawContent", ""),
        )


@dataclass
class FirecrawlScrapeResult:
    """Result from a Firecrawl scrape operation."""

    markdown: str = ""
    html: str = ""
    metadata: Optional[FirecrawlMetadata] = None
    success: bool = True
    error: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "FirecrawlScrapeResult":
        metadata_data = data.get("metadata", {})
        return cls(
            markdown=data.get("markdown", ""),
            html=data.get("html", ""),
            metadata=FirecrawlMetadata.from_dict(metadata_data)
            if metadata_data
            else None,
            success=data.get("success", True),
            error=data.get("error", ""),
        )


@dataclass
class FirecrawlSearchResult:
    """Result from a Firecrawl search operation."""

    title: str = ""
    url: str = ""
    description: str = ""
    markdown: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "FirecrawlSearchResult":
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            description=data.get("description", ""),
            markdown=data.get("markdown", ""),
        )


class FirecrawlClient:
    """Client for interacting with Firecrawl (cloud or self-hosted).

    Supports URL scraping, batch scraping, and search operations.

    Args:
        api_url: Firecrawl API URL. If not provided, reads from
            FIRECRAWL_API_URL env var (for self-hosted instances).
        api_key: Firecrawl API key. If not provided, reads from
            FIRECRAWL_API_KEY env var.
        timeout: Request timeout in seconds.

    Raises:
        ValueError: If no api_key is provided and FIRECRAWL_API_KEY is not set.

    Example:
        >>> # Self-hosted
        >>> client = FirecrawlClient(
        ...     api_url="http://localhost:3002",
        ...     api_key="your-api-key"
        ... )
        >>> result = client.scrape_url("https://example.com")
        >>> print(result.markdown[:200])
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_url = api_url or os.getenv("FIRECRAWL_API_URL", "")
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY", "")

        if not self.api_key:
            raise ValueError(
                "Please set the `FIRECRAWL_API_KEY` environment variable or pass "
                "api_key to FirecrawlClient."
            )

        self.timeout = timeout
        self._app = None

    def _get_app(self):
        """Get or create the FirecrawlApp instance."""
        if self._app is None:
            try:
                from firecrawl import FirecrawlApp

                if self.api_url:
                    self._app = FirecrawlApp(
                        api_url=self.api_url,
                        api_key=self.api_key,
                    )
                    logger.debug(
                        f"FirecrawlClient: Using self-hosted instance at {self.api_url}"
                    )
                else:
                    self._app = FirecrawlApp(api_key=self.api_key)
                    logger.debug("FirecrawlClient: Using cloud instance")
            except ImportError:
                raise ImportError(
                    "The 'firecrawl-py' package is not installed. "
                    "Please install it with 'pip install firecrawl-py'"
                )
        return self._app

    def scrape_url(
        self,
        url: str,
        formats: Optional[list[str]] = None,
        only_main_content: bool = True,
        include_tags: Optional[list[str]] = None,
        exclude_tags: Optional[list[str]] = None,
        headers: Optional[dict] = None,
        wait_for: int = 0,
    ) -> FirecrawlScrapeResult:
        """Scrape a single URL and return its content.

        Args:
            url: The URL to scrape.
            formats: Output formats to return. Defaults to ["markdown"].
            only_main_content: If True, only return the main content.
            include_tags: HTML tags to include in extraction.
            exclude_tags: HTML tags to exclude from extraction.
            headers: Custom HTTP headers to send with the request.
            wait_for: Time in milliseconds to wait for the page to load.

        Returns:
            FirecrawlScrapeResult with the scraped content.
        """
        import asyncio

        app = self._get_app()
        formats = formats or ["markdown"]

        kwargs = {
            "url": url,
            "formats": formats,
            "only_main_content": only_main_content,
        }
        if include_tags:
            kwargs["include_tags"] = include_tags
        if exclude_tags:
            kwargs["exclude_tags"] = exclude_tags
        if headers:
            kwargs["headers"] = headers
        if wait_for:
            kwargs["wait_for"] = wait_for

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    response = pool.submit(
                        lambda: app.scrape_url(**kwargs)
                    ).result(timeout=self.timeout)
            else:
                response = loop.run_until_complete(
                    self._async_scrape(app, **kwargs)
                )

            return FirecrawlScrapeResult.from_dict(
                response if isinstance(response, dict) else response.__dict__
            )
        except Exception as e:
            logger.error(f"Firecrawl scrape failed for {url}: {e}")
            return FirecrawlScrapeResult(
                success=False, error=str(e)
            )

    async def _async_scrape(self, app, **kwargs):
        """Async wrapper for scrape_url."""
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: app.scrape_url(**kwargs)
        )

    def scrape_urls(
        self,
        urls: list[str],
        formats: Optional[list[str]] = None,
        only_main_content: bool = True,
    ) -> list[FirecrawlScrapeResult]:
        """Scrape multiple URLs in batch.

        Args:
            urls: List of URLs to scrape.
            formats: Output formats. Defaults to ["markdown"].
            only_main_content: If True, only return main content.

        Returns:
            List of FirecrawlScrapeResult objects.
        """
        app = self._get_app()
        formats = formats or ["markdown"]

        try:
            response = app.batch_scrape_urls(
                urls,
                formats=formats,
                only_main_content=only_main_content,
            )
            return [
                FirecrawlScrapeResult.from_dict(r)
                for r in (response if isinstance(response, list) else [])
            ]
        except Exception as e:
            logger.error(f"Firecrawl batch scrape failed: {e}")
            return [
                FirecrawlScrapeResult(success=False, error=str(e))
                for _ in urls
            ]

    def search(
        self,
        query: str,
        limit: int = 10,
        scrape_options: Optional[dict] = None,
    ) -> list[FirecrawlSearchResult]:
        """Search for content using Firecrawl.

        Args:
            query: The search query.
            limit: Maximum number of results.
            scrape_options: Options for scraping found URLs.

        Returns:
            List of FirecrawlSearchResult objects.
        """
        app = self._get_app()

        try:
            response = app.search(
                query,
                limit=limit,
                scrape_options=scrape_options,
            )
            return [
                FirecrawlSearchResult.from_dict(r)
                for r in (response.get("data", []) if isinstance(response, dict) else [])
            ]
        except Exception as e:
            logger.error(f"Firecrawl search failed: {e}")
            return []

    def health_check(self) -> bool:
        """Check if the Firecrawl instance is healthy.

        Returns:
            True if the instance is healthy, False otherwise.
        """
        import httpx

        if not self.api_url:
            # Can't health-check cloud Firecrawl
            return True

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.api_url}/health")
                return response.status_code == 200
        except Exception:
            return False
