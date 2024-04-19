import logging
from typing import Iterator, Optional

import requests
from bs4 import BeautifulSoup

from r2r.core import DocumentPage, ScraperPipeline

logger = logging.getLogger(__name__)


def get_raw_html_from_url(url: str) -> str:
    try:
        response = requests.get(url)

        if response.status_code == 200:
            return response.text
        else:
            return (
                f"Failed to retrieve HTML. Status code: {response.status_code}"
            )
    except requests.exceptions.RequestException as e:
        return f"An error occurred: {e}"


class BasicScraperPipeline(ScraperPipeline):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def scrape_url(self, url: str) -> Iterator[DocumentPage]:
        """
        Scrape the given URL and return the raw data.
        """
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            yield DocumentPage(
                document_id=self.document_id,
                page_number=0,
                text=soup.get_text(),
                metadata={"url": url},
            )
        else:
            raise ValueError(
                f"Failed to retrieve HTML. Status code: {response.status_code}"
            )

    def run(
        self,
        document_id: str,
        url: str,
        metadata: Optional[dict] = {},
        **kwargs,
    ) -> Iterator[DocumentPage]:
        """
        Run the scraping method for the given URL.
        Yields the processed DocumentPage objects.
        """
        self.initialize_pipeline()
        self.document_id = document_id
        self.metadata = metadata

        if not url:
            raise ValueError("No URL provided to scrape.")

        yield from self.scrape_url(url)
