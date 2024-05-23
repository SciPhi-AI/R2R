import logging
import os
from typing import Optional, Union

from r2r.core import (
    VectorDBConfig,
    VectorDBProvider,
    VectorEntry,
    VectorSearchResult,
)

from r2r.vector_dbs.milvus.exception import CollectionNotInitializedError, MilvusDBInitializationError, \
    PymilvusImportError, MilvusCilentConnectionError, CollectionCreationError, CollectionDeletionError, \
    CollectionUpseartError

logger = logging.getLogger(__name__)


class MilvusVectorDB(VectorDBProvider):
    def __init__(self, config: VectorDBConfig) -> None:
        # initialize the vector db usage
        logger.info(
            "Initializing `MilvusVectorDB` to store and retrieve embeddings."
        )

        super().__init__(config)
        self.config = config
        if config.provider != "milvus":
            raise MilvusDBInitializationError(
                "MilvusVectorDB must be initialized with provider `milvus`."
            )

        # install pymilvus
        try:
            from pymilvus import MilvusClient
        except ImportError:
            raise PymilvusImportError(
                f"Error, `pymilvus` is not installed. Please install it using `pip install -U pymilvus`."
            )

        # set up milvus client information
        try:
            uri = os.getenv("MILVUS_URI")
            api_key = os.getenv("ZILLIZ_CLOUD_API_KEY")

            if not uri:
                raise MilvusCilentConnectionError(
                    "Error, MilvusVectorDB missing the MILVUS_URI environment variables."
                    "If you wish run it locally, please initialize it as local path file \"xxx.db\" in the current directory"
                    "If you wish to use cloud service, please add btoh uri as cloud endpoint and api_key as cloud api"
                )
            if api_key:
                self.client = MilvusClient(uri=uri, token=api_key)
            else:
                self.client = MilvusClient(uri)
        except Exception as e:
            raise MilvusCilentConnectionError(
                f"Error {e} occurred while attempting to connect to the milvus provider."
            )

    def initialize_collection(
        self, dimension: int
    ) -> None:
        """
        Initialize a collection.

        Parameters:
            collection_name: str
                The name of the collection.
            dimension: int
                The dimension of the collection.

        Returns:
            None
        """
        try:
            from pymilvus import DataType

            # create schema, with dynamic field available
            schema = self.client.create_schema(
                auto_id=False,
                enable_dynamic_field=True,
            )

            # add fields to schema
            schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
            schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dimension)

            # prepare index parameters
            index_params = self.client.prepare_index_params()
            index_params.add_index(index_type="AUTOINDEX", field_name="vector",
                                   metric_type="COSINE")

            # create a collection
            self.client.create_collection(
                collection_name=self.config.collection_name,
                schema=schema,
                index_params=index_params
            )

        except Exception as e:
            raise CollectionCreationError(
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
        if not self.client.has_collection(collection_name=self.config.collection_name):
            raise CollectionNotInitializedError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )

        data = {
            'id': entry.id,
            'vector': entry.vector,
        }

        for key, value in entry.metadata.items():
            data[key] = value

        try:
            # Can change to insert if upsert not working
            self.client.insert(
                collection_name=self.config.collection_name,
                data=data
            )
        except Exception as e:
            raise CollectionUpseartError(
                f"Upsert data failure cause exception {e} occurs."
            )

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Union[bool, int, str]] = {},
        limit: int = 10,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:
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

        filter_conditions = []
        for key, value in filters.items():
            if isinstance(value, str):
                filter_conditions.append(f"{key} like \"{value}\"")
            else:
                filter_conditions.append(f"{key} == {value}")

        if len(filter_conditions) == 1:
            filter = filter_conditions[0]
        else:
            filter = " and ".join(filter_conditions)

        results = self.client.search(
            collection_name=self.config.collection_name,
            data=[query_vector],
            filter=filter,
            limit=limit,
            *args,
            **kwargs,
        )[0]

        return [
            VectorSearchResult(
                str(result['id']), result['distance'], result['entity'] or {}
            )
            for result in results
        ]

    def create_index(self, index_type, column_name, index_options):
        pass

    def close(self):
        """
        close the milvus connection.
        """
        self.client.close()

    def filtered_deletion(
        self, key: str, value: Union[bool, int, str]
    ) -> None:
        """
        Delete entries from the collection based on a filtered condition.

        Parameters:
            key (str): The key to filter on.
            value (Union[bool, int, str]): The value to filter against.

        Raises:
            CollectionNotInitializedError: If the collection is not initialized before attempting deletion.
            CollectionDeletionError: If an error occurs during deletion.

        Returns:
            None
        """
        if not self.client.has_collection(collection_name=self.config.collection_name):
            raise CollectionNotInitializedError(
                "Please call `initialize_collection` before attempting to run `filtered_deletion`."
            )

        # Build filter condition based on value type
        if isinstance(value, str):
            filter = f"{key} like \"{value}\""
        else:
            filter = f"{key} == {value}"

        try:
            if key == 'id':
                self.client.delete(collection_name=self.config.collection_name,
                                   ids=value)
            else:
                self.client.delete(collection_name=self.config.collection_name,
                                   filter=filter)
        except Exception as e:
            raise CollectionDeletionError(f"Error {e} occurs in deletion of key value pair {self.config.collection_name}.")

    def get_all_unique_values(
        self,
        metadata_field: str,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> list[str]:
        """
        Retrieve all unique values of a metadata field, optionally filtered by another field-value pair.
        # 取在filter_field是filter_value下的metadata_field

        Parameters:
            metadata_field (str): The metadata field for which unique values are to be retrieved.
            filter_field (Optional[str]): The field to filter on. Defaults to None.
            filter_value (Optional[str]): The value to filter against. Defaults to None.

        Raises:
            CollectionNotInitializedError: If the collection is not initialized before attempting retrieval.

        Returns:
            list[str]: A list of unique values of the specified metadata field.
        """
        if not self.client.has_collection(collection_name=self.config.collection_name):
            raise CollectionNotInitializedError(
                "Please call `initialize_collection` before attempting to run `filtered_deletion`."
            )

        # Build filter condition based on value type
        if filter_field is not None and filter_value is not None:
            filter = f"{filter_field} like \"{filter_value}\""
        else:
            filter = None

        unique_values = []
        results = self.client.query(
            collection_name=self.config.collection_name,
            filter=filter,
            output_fields=[metadata_field],
        )

        for result in results:
            unique_values.append(result[metadata_field])

        return unique_values
