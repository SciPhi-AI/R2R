import logging
import os
from typing import Optional, Union

from r2r.core import (
    VectorDBConfig,
    VectorDBProvider,
    VectorEntry,
    SearchResult,
)

from pymilvus import DataType

logger = logging.getLogger(__name__)

GET_ALL_LIMIT = 1000
# Set up test with:
# os.environ["MILVUS_URI"] = "./milvus_lite_demo1.db"

# Local Docker pass all tests, but lite version fail on get_metadatas() without filters
# Fix this issue soon

class MilvusVectorDB(VectorDBProvider):
    def __init__(self, config: VectorDBConfig) -> None:
        # initialize the vector db usage
        logger.info(
            "Initializing `MilvusVectorDB` to store and retrieve embeddings."
        )

        super().__init__(config)
        self.config = config
        if config.provider != "milvus":
            raise ValueError(
                "MilvusVectorDB must be initialized with provider `milvus`."
            )

        # install pymilvus
        try:
            from pymilvus import MilvusClient
        except ImportError:
            raise ValueError(
                f"Error, `pymilvus` is not installed. Please install it using `pip install -U pymilvus`."
            )

        # set up milvus client information
        try:
            uri = os.getenv("MILVUS_URI")
            api_key = os.getenv("ZILLIZ_CLOUD_API_KEY")

            if not uri:
                raise ValueError(
                    "Error, MilvusVectorDB missing the MILVUS_URI environment variables."
                    'If you wish run it locally, please initialize it as local path file "xxx.db" in the current directory'
                    "If you wish to use cloud service, please add btoh uri as cloud endpoint and api_key as cloud api"
                )
            self.client = MilvusClient(uri=uri, token=api_key)
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to the milvus provider."
            )

    def initialize_collection(self, dimension: int) -> None:
        """
        Initialize a collection.

        Parameters:
            dimension: int
                The dimension of the collection.

        Returns:
            None
        """
        try:
            # create schema, with dynamic field available
            schema = self.client.create_schema(
                auto_id=False,
                enable_dynamic_field=True,
            )

            # add fields to schema
            schema.add_field(
                field_name="id",
                datatype=DataType.VARCHAR,
                is_primary=True,
                max_length=36,
            )
            schema.add_field(
                field_name="vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=dimension,
            )

            # prepare index parameters
            index_params = self.client.prepare_index_params()
            index_params.add_index(
                index_type="AUTOINDEX",
                field_name="vector",
                metric_type="COSINE",
            )

            # create a collection
            self.client.create_collection(
                collection_name=self.config.collection_name,
                schema=schema,
                index_params=index_params,
                consistency_level=0
            )

        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to creat collection {self.config.collection_name}."
            )

    def copy(self, entry: VectorEntry, commit: bool = True) -> None:
        pass

    def upsert(self, entry: VectorEntry, commit: bool = True) -> None:
        """
        Update or insert a vector entry into the collection.

        Parameters:
            entry (VectorEntry): The vector entry to be updated or inserted.
            commit (bool, optional): Whether to commit the upsert operation immediately. Defaults to True.

        Raises:
            CollectionNotInitializedError: If the collection is not initialized before attempting to run `upsert`.

        Returns:
            None
        """
        if not self.client.has_collection(
            collection_name=self.config.collection_name
        ):
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )

        data = {
            "id": str(entry.id),
            "vector": entry.vector.data,
        }

        for key, value in entry.metadata.items():
            data[key] = value

        try:
            # Can change to insert if upsert not working
            self.client.upsert(
                collection_name=self.config.collection_name, data=data
            )
        except Exception as e:
            raise ValueError(
                f"Upsert data failure cause exception {e} occurs."
            )

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Union[bool, int, str]] = {},
        limit: int = 10,
        *args,
        **kwargs,
    ) -> list[SearchResult]:
        """
        Perform a vector search operation.

        Parameters:
            query_vector (list[float]): The vector representing the query.
            filters (dict[str, Union[bool, int, str]], optional): Filters to apply to the search results. Defaults to {}.
            limit (int, optional): The maximum number of results to return. Defaults to 10.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            list[VectorSearchResult]: A list of search results.
        """
        if filters:
            filter_conditions = []
            for key, value in filters.items():
                filter_conditions.append(self.build_filter(key, value))

            if len(filter_conditions) == 1:
                filter_expression = filter_conditions[0]
            else:
                filter_expression = " and ".join(filter_conditions)
        else:
            filter_expression = None

        results = self.client.search(
            collection_name=self.config.collection_name,
            data=[query_vector],
            filter=filter_expression,
            limit=limit,
            output_fields=["*"],
            *args,
            **kwargs,
        )[0]

        return [
            SearchResult(
                id=result["id"],
                score=float(result["distance"]),
                metadata=result["entity"] or {},
            )
            for result in results
        ]

    def create_index(self, index_type, column_name, index_options):
        pass

    def delete_by_metadata(
        self, metadata_field: str, metadata_value: Union[bool, int, str]
    ) -> None:
        """
        Delete entries from the collection based on a filtered condition.

        Parameters:
            metadata_field (str): The key to filter on.
            metadata_value (Union[bool, int, str]): The value to filter against.

        Raises:
            CollectionNotInitializedError: If the collection is not initialized before attempting deletion.
            CollectionDeletionError: If an error occurs during deletion.

        Returns:
            None
        """
        if not self.client.has_collection(
            collection_name=self.config.collection_name
        ):
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `filtered_deletion`."
            )

        try:
            self.client.delete(
                collection_name=self.config.collection_name,
                filter=self.build_filter(metadata_field, metadata_value),
            )
        except Exception as e:
            raise ValueError(
                f"Error {e} occurs in deletion of key value pair {self.config.collection_name}."
            )

    def get_metadatas(
        self,
        metadata_fields: list[str],
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> list[dict]:
        """
        Retrieve all unique values of a metadata field, optionally filtered by another field-value pair.

        Parameters:
            metadata_fields (str): The metadata field for which unique values are to be retrieved.
            filter_field (Optional[str]): The field to filter on. Defaults to None.
            filter_value (Optional[str]): The value to filter against. Defaults to None.

        Raises:
            CollectionNotInitializedError: If the collection is not initialized before attempting retrieval.

        Returns:
            list[str]: A list of unique values of the specified metadata field.
        """
        if not self.client.has_collection(
            collection_name=self.config.collection_name
        ):
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `filtered_deletion`."
            )

        # Build filter condition based on value type
        if filter_field is not None and filter_value is not None:
            filter_expression = f'{filter_field} == "{filter_value}"'
        else:
            filter_expression = ''

        unique_values = []
        if not filter_expression:
            results = self.client.query(
                collection_name=self.config.collection_name,
                filter=filter_expression,
                consistency_level=0,
                output_fields=metadata_fields,
                limit=GET_ALL_LIMIT
            )
        else:
            results = self.client.query(
                collection_name=self.config.collection_name,
                filter=filter_expression,
                output_fields=metadata_fields,
            )
        for result in results:
            unique_values.append(result)
        return unique_values

    @staticmethod
    def build_filter(key, value) -> str:
        if isinstance(value, str):
            filter_expression = f'{key} == "{value}"'
        else:
            filter_expression = f"{key} == {value}"

        return filter_expression
