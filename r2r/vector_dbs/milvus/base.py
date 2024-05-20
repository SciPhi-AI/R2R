import logging
import os
from typing import Optional, Union

from pymilvus import DataType
from pymilvus.milvus_client import IndexParams

from r2r.core import (
    VectorDBConfig,
    VectorDBProvider,
    VectorEntry,
    VectorSearchResult,
)
from r2r.vecs.client import Client
from r2r.vecs.collection import Collection, MetadataValues

logger = logging.getLogger(__name__)

class MilvusVectorDB(VectorDBConfig):
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
            api_key = os.getenv("MILVUS_API_KEY")

            if not uri:
                raise ValueError(
                    "Error, MilvusVectorDB missing the MILVUS_URI environment variables."
                    "If you wish run it locally, please initialize it as local path file \"xxx.db\" in the current directory"
                    "If you wish to use cloud service, please add btoh uri as cloud endpoint and api_key as cloud api"
                )

            self.client = MilvusClient(uri=uri, api_key=api_key)
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to connect to the milvus provider."
            )

    def initialize_collection(
        self, dimension: int
    ) -> None:
        """
        Initialize a collection.

        TODO:
        Adding pre set schema and indexing right now, need to decide how to adjust this.

        Parameters:
            collection_name: str
                The name of the collection.
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
            schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
            schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dimension)

            # prepare index parameters
            param = self.client.prepare_index_params()
            index_params = self.create_index(index_params=param, index_type="AUTOINDEX",
                                             field_name="vector", metric_type="COSINE")

            # create a collection
            self.client.create_collection(
                collection_name=self.config.collection_name,
                schema=schema,
                index_params=index_params
            )

            # TODO: 商讨是否使用这一种简便的创造方法
            # self.client.create_collection(
            #     collection_name=collection_name,
            #     dimension=dimension,
            #     enable_dynamic_field=True,
            # )
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to creat colelction {self.config.collection_name}."
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
            ValueError: If the collection is not initialized before attempting to run `upsert`.

        TODO:
            Determine how to handle metadata.
            - Currently, only 'id' and 'vector' fields are included in the data dictionary.
            - Decide how to incorporate metadata into the `upsert` operation.

        Returns:
            None
        """
        if not self.client.has_collection(collection_name=self.config.collection_name):
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )

        # TODO：该如何处理metadata
        data = {
            'id': entry.to_json()['id'],
            'vector': entry.to_json()['vector'],
        }

        # 测试如果不行改成insert
        self.client.upsert(
            collection_name=self.config.collection_name,
            data=data
        )

    def search(
        self,
        query_vector: list[float],
        filters: dict[str, Union[bool, int, str]] = {},
        limit: int = 10,
        *args,
        **kwargs,
    ) -> list[VectorSearchResult]:

        # TODO: 处理filters
        results = self.client.search(
            collection_name=self.config.collection_name,
            data=query_vector,
            limit=limit,
            *args,
            **kwargs,
        )

        return [
            VectorSearchResult(
                str(result['id']), result['distance'], result['entity'] or {}
            )
            for result in results
        ]

    def create_index(
            self,
            index_params: IndexParams,
            index_type: str,
            field_name: str,
            metric_type: str,
            index_name: str = None,
            params: dict = None,
    ) -> IndexParams:
        """
        Add indexes to the index parameters.

        Parameters:
            index_params: IndexParams
                The index parameters object to which the index will be added.
            index_type: str
                The type of index to be added.
            field_name: str
                The name of the field for which the index will be added.
            metric_type: str
                The type of metric to be used for the index.
            index_name: str, optional
                The name of the index. Defaults to None.
            params: dict, optional
                Additional parameters for the index. Defaults to None.

        Returns:
            IndexParams: The updated index parameters.
        """
        index_params.add_index(
            field_name=field_name,
            index_type=index_type,
            metric_type=metric_type,
            index_name=index_name,
            params=params,
        )

        return index_params

    def close(self):
        """
        close the milvus connection.
        """
        self.client.close()

    def upsert_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        for entry in entries:
            self.upsert(entry, commit=commit)

    def copy_entries(
        self, entries: list[VectorEntry], commit: bool = True
    ) -> None:
        for entry in entries:
            self.copy(entry, commit=commit)

    def filtered_deletion(
        self, key: str, value: Union[bool, int, str]
    ) -> None:
        pass

    def get_all_unique_values(
        self,
        metadata_field: str,
        filter_field: Optional[str] = None,
        filter_value: Optional[str] = None,
    ) -> list[str]:
        pass