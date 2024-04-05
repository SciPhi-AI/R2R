import logging
from r2r.core import ScrapingPipeline
from r2r.core import BasicDocument

from typing import Iterator, Optional

logger = logging.getLogger(__name__)

class BasicScrapingPipeline(ScrapingPipeline):
    def __init__(self, *args, **kwargs):
        logger.info("Initializing a `BasicScrapingPipeline` to scrape URLs.")
        super().__init__(*args, **kwargs)
        
    def scrape_url(self, url: str) -> Iterator[BasicDocument]:
        """
        Scrape the given URL and return the raw data.
        """
        # TODO: Implement
        yield BasicDocument(id=1, text="Hello, world!", metadata={"url": url})

    def run(self, document_id: str, url: str, metadata: Optional[dict] = {}, **kwargs) -> Iterator[BasicDocument]:
        """
        Run the scraping method for the given URL.
        Yields the processed BasicDocument objects.
        """
        self.initialize_pipeline()
        self.document_id = document_id
        self.metadata = metadata

        if not url:
            raise ValueError("No URL provided to scrape.")

        yield from self.scrape_url(url)