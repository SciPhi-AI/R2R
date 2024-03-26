import logging
import os
from typing import Optional, Union

from r2r.core import VectorDBProvider, VectorEntry, VectorSearchResult

logger = logging.getLogger(__name__)


class LanceDB(VectorDBProvider):
    def __init__(
            self, provider: str = "lancedb", db_path: Optional[str] = None
    ) -> None:
        logger.info("Initializing `LanceDB` to store and retrieve embeddings.")

        super().__init__(provider)
        if provider != "lancedb":
            raise ValueError(
                "LanceDB must be initialized with provider `lancedb`."
            )
        try:
            import lancedb
        except ImportError:
            raise ValueError(
                f"Error, `lancedb` is not installed. Please install it using `pip install lancedb`."
            )
        self.db_path = db_path
        try:
            self.client = lancedb.connect(db_path=self.db_path)
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to the lancedb provider."
            )
        self.collection_name: Optional[str] = None

    def initialize_collection(
            self, collection_name: str, dimension: int
    ) -> None:
        self.collection_name = collection_name
        try:
            import pyarrow  # TODO ADD Dependency
        except ImportError:
            raise ValueError(
                f"Error, `pyarrow` is not installed. Please install it using `pip install pyarrow`."
            )
        try:
            result = self.client.create_table(
                name=f"{collection_name}", on_bad_vectors="error", schema=[]
            )
        except Exception:
            # TODO - Handle more appropriately - create collection fails when it already exists
            # https://lancedb.github.io/lancedb/python/python/#lancedb.db.DBConnection.create_table
            print(Exception)
            pass
