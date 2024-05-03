import logging
import os
from typing import Optional, Union, Any, Dict, str

from r2r.core import (
    VectorDBConfig,
    VectorDBProvider,
    VectorEntry,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)

def _to_lance_filter(filter: Dict[str,Any]) -> Any:
    """Translate standard metadata filters to Lance specific spec."""
    filters = []
    for key,value in filter.items():
        if isinstance(value,str):
            filters.append(key+'= "' + value + '"')
        else :
            filters.append(key + '= "' + str(value) + '"')
    
    return " AND ".join(filters)

class LanceDB(VectorDBProvider):
    def __init__(self, config: VectorDBConfig) -> None:
        logger.info("Initializing `LanceDB` to store and retrieve embeddings.")

        super().__init__(config)
        if config.provider != "lancedb":
            raise ValueError("LanceDB must be initialized with provider `lancedb`.")

        try:
            import lancedb

            api_key = os.getenv("LANCEDB_API_KEY")
            uri = os.getenv("LANCEDB_URI") or '/lancedb'
            region = os.getenv("LANCE_REGION") 

            if uri.startswith("db://") and api_key is None:
                raise ValueError("API key is required for LanceDB cloud.")

            self.client = lancedb.connect(uri, api_key=api_key, region=region)

        except ImportError:
            raise ValueError(
                "Error, `lancedb` is not installed. Please install it using `pip install lancedb`."
            )

    def initialize_collection(self, dims: int) -> None:
        try:
            # TODO - create table via pa schema with dims as embedding size
            import pyarrow as pa

            schema = pa.schema(
                [
                    pa.field(
                        "vector",
                        pa.list_(
                            pa.float32(),
                            dims,  # type: ignore
                        ),
                    ),
                    pa.field("id", pa.string()),
                    pa.field("metadata", pa.string()),
                ]
            )
            self.collection = self.client.create_table(
                name=self.config.collection_name, schema=schema
            )
        except Exception:
            # TODO - Handle more appropriately - create collection fails when it already exists
            pass

    def copy(self, entry: VectorEntry, commit=True) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )
        self.upsert(entry=entry,mode='append')

    def upsert(self, entry: VectorEntry, mode: Optional[str] = "overwrite") -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )
        try:
            data = [
                {
                    "id": str(entry.id),
                    "vector": list([float(ele) for ele in entry.vector]),
                    "metadata": entry.metadata,
                }
            ]
            self.collection.add(
                data=data,
                mode=mode,
            )
        except Exception as e:
            raise e

    def upsert_entries(
        self,
        entries: list[VectorEntry],
        mode: Optional[str] = "overwrite",
    ) -> None:
        if self.collection is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )

        data = [
            {
                "id": str(entry.id),
                "vector": list([float(ele) for ele in entry.vector]),
                "metadata": entry.metadata,
            }
            for entry in entries
        ]
        self.collection.add(
            data=data,
            mode=mode,
        )

    def search(
            self,
            query_vector: list[float],
            filters: dict[str, Union[bool, int, str]] = {},
            limit: int = 10,
            prefilter : Optional[bool] = False,
            **kwargs,
        ) -> list[VectorSearchResult]:
            """
            Perform a vector search in the LanceDB collection.
            Args:
                query_vector (list[float]): The query vector to search for.
                filters (dict[str, Union[bool, int, str]], optional): Filters to apply to the search. Defaults to {}.
                limit (int, optional): The maximum number of results to return. Defaults to 10.
                prefilter (bool, optional) : if True then applies filter before search
                **kwargs: Additional keyword arguments for search. 
                            Options :
                                nprobes (int, optional): The number of probes used.
                                    A higher number makes search more accurate but also slower.
                                    Defaults to 20.
                                refine_factor: (int, optional): Refine the results by reading extra elements
                                    and re-ranking them in memory.
                                    Defaults to None
                                    
            Returns:
                list[VectorSearchResult]: A list of VectorSearchResult objects representing the search results.
            """
            if self.config.collection_name is None:
                raise ValueError(
                    "Please call `initialize_collection` before attempting to run `search`."
                )

            if filters != {}: 
                where = _to_lance_filter(filters)
            
            lance_query = self.collection.search(
                query=query_vector,
                vector_column_name='vector'
            ).where(where).limit(limit)

            if kwargs:
                if kwargs.get('nprobes',None) :
                    lance_query.nprobes(kwargs.pop('nprobes'))
                if kwargs.get('refine_factor',None):
                    lance_query.refine_factor(kwargs.pop('refine_factor'))
         
            results = lance_query.to_arrow()

            return [
                VectorSearchResult(str(result.id), result._distance, result.metadata or {})
                for result in results
            ]

    def create_index(
        self,
        index_type,
        column_name,
        metric: Optional[int] = "L2",
        num_partitions: Optional[int] = 256,
        num_sub_vectors: Optional[int] = 96,
        index_cache_size: Optional[int] = None,
    ):
        """
        Create an index on the specified column in the database.

        Args:
            index_type (str): The type of index to create. Valid values are 'vector' or 'scalar'.
            column_name (str): The name of the column on which to create the index.
            metric (Optional[str]): The metric to use for vector index. Valid values are "L2", "cosine", or "dot".
                                    Default is 'L2'.
            num_partitions (Optional[int]): The number of partitions for vector index. Default is 256.
            num_sub_vectors (Optional[int]): The number of sub-vectors for vector index. Default is 96.
            index_cache_size (Optional[int]): The cache size for the index. Default is None.

        Raises:
            ValueError: If an invalid index_type is provided.

        Returns:
            None
        """

        if index_type == "vector":
            self._connection.create_index(
                metric=metric,
                vector_column_name=column_name,
                num_partitions=num_partitions,
                num_sub_vectors=num_partitions,
                index_cache_size=index_cache_size,
            )
        elif index_type == "scalar":
            self._connection.create_scalar_index(column_name)
        else:
            raise ValueError(
                "Provide either vector/scalar in index_type,\
                             Also pass in index options (num_partitions,num_subvectors and index_cache_size) for vector index creation"
            )

    def close(self):
        pass

    def filtered_deletion(self, key: str, value: Union[bool, int, str]) -> None:
        if self.config.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `filtered_deletion`."
            )

        # TODO: filtered deletion
        return

    def get_all_unique_values(
        self,
        metadata_field: str,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> list:
        if self.config.collection_name is None:
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `get_all_unique_values`."
            )   
        # TODO: drop duplicates / efficient in polars mabye
        unique_values = []
        
        return list(unique_values)
