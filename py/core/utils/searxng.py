"""SearxNG client for web search and content extraction.

SearxNG is a free internet metasearch engine which aggregates results from
various search services and databases. This client supports both local and
remote SearxNG instances.

Usage:
    # Set environment variable
    export SEARXNG_BASE_URL=http://localhost:8888

    # Or pass directly
    client = SearxNGClient(base_url="http://localhost:8888")
    results = client.search("python programming")
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearxNGSearchResult:
    """A single search result from SearxNG."""

    title: str
    url: str
    content: str
    engine: str = ""
    score: float = 0.0
    category: str = ""
    parsed_url: list[str] = field(default_factory=list)
    engines: list[str] = field(default_factory=list)
    positions: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "SearxNGSearchResult":
        """Create a SearxNGSearchResult from a dictionary."""
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            content=data.get("content", ""),
            engine=data.get("engine", ""),
            score=data.get("score", 0.0),
            category=data.get("category", ""),
            parsed_url=data.get("parsed_url", []),
            engines=data.get("engines", []),
            positions=data.get("positions", []),
        )


@dataclass
class SearxNGSearchResponse:
    """Response from a SearxNG search query."""

    query: str
    results: list[SearxNGSearchResult] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    infoboxes: list[dict] = field(default_factory=list)
    number_of_results: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "SearxNGSearchResponse":
        """Create a SearxNGSearchResponse from a dictionary."""
        return cls(
            query=data.get("query", ""),
            results=[
                SearxNGSearchResult.from_dict(r)
                for r in data.get("results", [])
            ],
            suggestions=data.get("suggestions", []),
            answers=data.get("answers", []),
            infoboxes=data.get("infoboxes", []),
            number_of_results=data.get("number_of_results", 0),
        )


class SearxNGClient:
    """Client for interacting with a SearxNG instance.

    Supports search and content extraction operations against a self-hosted
    or remote SearxNG instance.

    Args:
        base_url: The base URL of the SearxNG instance.
            If not provided, reads from SEARXNG_BASE_URL environment variable.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retry attempts for failed requests.

    Raises:
        ValueError: If no base_url is provided and SEARXNG_BASE_URL is not set.

    Example:
        >>> client = SearxNGClient(base_url="http://localhost:8888")
        >>> results = client.search("python programming", max_results=5)
        >>> for result in results.results:
        ...     print(f"{result.title}: {result.url}")
    """

    # Default SearxNG engines to use
    DEFAULT_ENGINES = ["google", "bing", "duckduckgo"]

    # Default categories
    DEFAULT_CATEGORIES = ["general"]

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = (base_url or os.getenv("SEARXNG_BASE_URL", "")).rstrip(
            "/"
        )
        if not self.base_url:
            raise ValueError(
                "Please set the `SEARXNG_BASE_URL` environment variable or pass "
                "base_url to SearxNGClient to use the SearxNG search engine."
            )

        self.timeout = timeout
        self.max_retries = max_retries

    def _build_search_url(self, **params) -> str:
        """Build the search URL with query parameters."""
        query_parts = []
        for key, value in params.items():
            if value is not None and value != "":
                if isinstance(value, list):
                    value = ",".join(str(v) for v in value)
                query_parts.append(f"{key}={value}")
        return f"{self.base_url}/search?{'&'.join(query_parts)}"

    def search(
        self,
        query: str,
        max_results: int = 10,
        categories: Optional[list[str]] = None,
        engines: Optional[list[str]] = None,
        language: str = "en",
        time_range: Optional[str] = None,
        safesearch: int = 0,
    ) -> SearxNGSearchResponse:
        """Perform a search query on SearxNG.

        Args:
            query: The search query string.
            max_results: Maximum number of results to return.
            categories: List of categories to search in.
                Defaults to ["general"].
            engines: List of specific engines to use.
                Defaults to ["google", "bing", "duckduckgo"].
            language: Language code for search results.
            time_range: Time range filter (day, week, month, year).
            safesearch: Safe search level (0=off, 1=moderate, 2=strict).

        Returns:
            SearxNGSearchResponse containing search results.
        """
        import httpx

        categories = categories or self.DEFAULT_CATEGORIES
        engines = engines or self.DEFAULT_ENGINES

        params = {
            "q": query,
            "format": "json",
            "categories": ",".join(categories),
            "engines": ",".join(engines),
            "language": language,
            "safesearch": safesearch,
        }
        if time_range:
            params["time_range"] = time_range

        url = self._build_search_url(**params)
        logger.debug(f"SearxNG search: {url}")

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
                return SearxNGSearchResponse.from_dict(data)
        except httpx.TimeoutException:
            logger.error(f"SearxNG search timed out after {self.timeout}s")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"SearxNG search failed with status {e.response.status_code}: {e}")
            raise
        except Exception as e:
            logger.error(f"SearxNG search failed: {e}")
            raise

    def extract_content(
        self,
        url: str,
        engines: Optional[list[str]] = None,
    ) -> Optional[str]:
        """Extract content from a URL using SearxNG's fetch functionality.

        Note: This uses SearxNG's built-in page fetcher if available.
        For more reliable extraction, consider using dedicated extraction tools.

        Args:
            url: The URL to extract content from.
            engines: Engines to use for extraction.

        Returns:
            Extracted content as a string, or None if extraction fails.
        """
        import httpx

        params = {
            "url": url,
            "format": "json",
        }
        if engines:
            params["engines"] = ",".join(engines)

        fetch_url = f"{self.base_url}/fetch"
        logger.debug(f"SearxNG fetch: {fetch_url}")

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(fetch_url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("content", "")
        except Exception as e:
            logger.warning(f"SearxNG content extraction failed for {url}: {e}")
            return None

    def get_engines(self) -> list[dict]:
        """Get list of available engines on the SearxNG instance.

        Returns:
            List of engine information dictionaries.
        """
        import httpx

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}/config")
                response.raise_for_status()
                data = response.json()
                return data.get("engines", [])
        except Exception as e:
            logger.warning(f"Failed to get SearxNG engines: {e}")
            return []

    def get_categories(self) -> list[str]:
        """Get list of available categories on the SearxNG instance.

        Returns:
            List of category names.
        """
        import httpx

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(f"{self.base_url}/config")
                response.raise_for_status()
                data = response.json()
                return data.get("categories", [])
        except Exception as e:
            logger.warning(f"Failed to get SearxNG categories: {e}")
            return []

    def health_check(self) -> bool:
        """Check if the SearxNG instance is healthy.

        Returns:
            True if the instance is healthy, False otherwise.
        """
        import httpx

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/healthz")
                return response.status_code == 200
        except Exception:
            return False
