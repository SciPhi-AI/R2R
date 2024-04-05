from abc import abstractmethod
from typing import Any, Iterator, Optional

from ..abstractions.document import BasicDocument
from ..providers.logging import LoggingDatabaseConnection
from ..utils import generate_run_id
from .pipeline import Pipeline


class ScrapingPipeline(Pipeline):
    def __init__(
        self,
        logging_connection: Optional[LoggingDatabaseConnection] = None,
        *args,
        **kwargs,
    ):
        super().__init__(logging_connection=logging_connection, **kwargs)

    def initialize_pipeline(self, *args, **kwargs) -> None:
        self.pipeline_run_info = {
            "run_id": generate_run_id(),
            "type": "scraping",
        }

    def scrape_url(self, url: str) -> Iterator[BasicDocument]:
        """
        Scrape the given URL and return the raw data.
        """
        pass


    def run(self, url: str, **kwargs) -> Iterator[BasicDocument]:
        """
        Run the scraping method for the given URL.
        Yields the processed BasicDocument objects.
        """
        pass