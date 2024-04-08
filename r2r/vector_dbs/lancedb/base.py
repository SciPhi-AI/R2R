import logging
import os
from typing import Optional, Union

from r2r.core import VectorDBProvider, VectorEntry, VectorSearchResult

logger = logging.getLogger(__name__)


class LanceDB(VectorDBProvider):
    # TODO enable LanceDB provider to support lanceDB Cloud
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
            self.client = lancedb.connect(uri=self.db_path or os.environ.get("LANCEDB_URI"))
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
            import pyarrow
        except ImportError:
            raise ValueError(
                f"Error, `pyarrow` is not installed. Please install it using `pip install pyarrow`."
            )

        table_schema = pyarrow.schema(
            [
                pyarrow.field("id", pyarrow.string()),
                pyarrow.field(
                    "vector", pyarrow.list_(pyarrow.float32(), dimension)
                ),
                # TODO Handle storing metadata
            ]
        )

        try:
            self.client.create_table(
                name=f"{collection_name}",
                on_bad_vectors="error",
                schema=table_schema,
            )
        except Exception as e:
            # TODO - Handle more appropriately - create collection fails when it already exists
            pass

    def copy(self, entry: VectorEntry, commit=True) -> None:
        raise NotImplementedError(
            "LanceDB does not support the `copy` method."
        )

    def upsert(self, entry: VectorEntry, commit=True) -> None:
        if self.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )
        self.client.open_table(self.collection_name).add(
            {
                "vector": entry.vector,
                "id": entry.id,
                # TODO ADD metadata storage
            },
            mode="overwrite",
        )

    def upsert_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        pass

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Union[bool, int, str]] = {},
        limit: int = 10,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
        pass

    def create_index(self, index_type, column_name, index_options):
        pass

    def close(self):
        pass

    def filtered_deletion(
        self, key: str, value: Union[bool, int, str]
    ) -> None:
        pass

    def get_all_unique_values(
        self, collection_name: str, metadata_field: str, filters: dict = {}
    ) -> list:
        pass
