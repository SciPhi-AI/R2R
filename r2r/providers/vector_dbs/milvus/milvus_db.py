import json
import logging
import os
import uuid
from typing import Optional, Union, List

from r2r.core import (
    VectorDBConfig,
    VectorDBProvider,
    VectorEntry,
    SearchResult,
)
from r2r.core.abstractions.document import DocumentInfo

from pymilvus import DataType

from r2r.core.abstractions.user import UserStats

logger = logging.getLogger(__name__)

GET_ALL_LIMIT = 1000
# Set up test with:
os.environ["MILVUS_URI_KEY"] = "./milvus_lite_demo1.db"
# os.environ["MILVUS_URI_KEY"] = "http://10.100.30.11:19530"
# os.environ["OPENAI_API_KEY"] =

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
            uri = os.getenv("MILVUS_URI_KEY")
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

            # create vector collection
            self.client.create_collection(
                collection_name=self.config.collection_name,
                schema=schema,
                index_params=index_params,
                consistency_level=0,
            )
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to creat collection {self.config.collection_name}."
            )

        # TODO: 解决不插入vector的问题
        try:
            # create schema, with dynamic field available
            schema_doc = self.client.create_schema(
                auto_id=False,
                enable_dynamic_field=True,
            )

            # add fields to schema
            schema.add_field(
                field_name="document_id",
                datatype=DataType.VARCHAR,
                is_primary=True,
                max_length=36,
            )

            # prepare index parameters
            index_params_doc = self.client.prepare_index_params()
            index_params_doc.add_index(
                index_type="AUTOINDEX",
                field_name="document_id",
            )

            # create vector collection
            self.client.create_collection(
                collection_name=f"document_info_{self.config.collection_name}",
                schema=schema_doc,
                index_params=index_params_doc,
                consistency_level=0,
            )
        except Exception as e:
            raise ValueError(
                f"Error {e} occurred while attempting to creat collection document_info_{self.config.collection_name}."
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

        data = entry.to_serializable()

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
        filter_expressions = []
        if filters:
            for key, value in filters.items():
                filter_expression = self.build_filter(key, value)
                filter_expressions.append(filter_expression)
            filter_expression = ' and '.join(filter_expressions)
        else:
            filter_expression = ''

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
                metadata=result["entity"]["metadata"] or {},
            )
            for result in results
        ]

    def create_index(self, index_type, column_name, index_options):
        pass

    def delete_by_metadata(
        self,
        metadata_fields: list[str],
        metadata_values: list[Union[bool, int, str]],
    ) -> list[str]:
        """
        Delete entries from the collection based on a filtered condition.

        Parameters:
            metadata_fields (list[str]): The key to filter on.
            metadata_values (list[Union[bool, int, str]]): The value to filter against.

        Raises:
            CollectionNotInitializedError: If the collection is not initialized before attempting deletion.
            CollectionDeletionError: If an error occurs during deletion.

        Returns:
            list[str]: A list of id that have been deleted
        """
        super().delete_by_metadata(metadata_fields, metadata_values)
        if not self.client.has_collection(
            collection_name=self.config.collection_name
        ):
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `filtered_deletion`."
            )

        filter_expressions = []
        for i in range(len(metadata_fields)):
            filter = self.build_filter(metadata_fields[i], metadata_values[i])
            filter_expressions.append(filter)

        result = []

        try:
            for i in range(len(filter_expressions)):
                res = self.client.delete(
                    collection_name=self.config.collection_name,
                    filter=filter_expressions[i],
                )
                for id_ in res:
                    result.append(id_)

        except Exception as e:
            raise ValueError(
                f"Error {e} occurs in deletion of key value pair {self.config.collection_name}."
            )

        return result

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
            if filter_field == 'id':
                filter_expression = f'{filter_field} == "{filter_value}"'
            else:
                filter_expression = self.build_filter(filter_field, filter_value)
        else:
            filter_expression = ""

        unique_values = []
        if not filter_expression:
            results = self.client.query(
                collection_name=self.config.collection_name,
                filter=filter_expression,
                consistency_level=0,
                output_fields=['metadata'],
                limit=GET_ALL_LIMIT,
            )
        else:
            results = self.client.query(
                collection_name=self.config.collection_name,
                filter=filter_expression,
                output_fields=['metadata'],
            )

        for result in results:
            res = dict()
            for field in metadata_fields:
                res[field] = result[field]
            unique_values.append(res)

        return unique_values

    @staticmethod
    def build_filter(key, value) -> str:
        if isinstance(value, str):
            filter_expression = f'metadata["{key}"] == "{value}"'
        else:
            filter_expression = f'metadata["{key}"] == {value}'

        return filter_expression

    # TODO: Need future discussion of implementation
    #       Need to adjust the storing collection
    def upsert_documents_info(self, document_infs: list[DocumentInfo]) -> None:
        if not self.client.has_collection(
            collection_name=f"document_info_{self.config.collection_name}"
        ):
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `upsert`."
            )

        document_data = []

        for document_inf in document_infs:
            data = document_inf.convert_to_db_entry()
            document_data.append(data)

        try:
            # Can change to insert if upsert not working
            self.client.upsert(
                collection_name=f"document_info_{self.config.collection_name}", data=document_data
            )
        except Exception as e:
            raise ValueError(
                f"Upsert data failure cause exception {e} occurs."
            )

    def get_documents_info(
        self,
        filter_document_ids: Optional[list[str]] = None,
        filter_user_ids: Optional[list[str]] = None,
    ) -> list[DocumentInfo]:

        filter_expressions = []
        if filter_document_ids:
            for id_ in filter_document_ids:
                filter_expressions.append(f'document_id == "{id_}"')

        if filter_user_ids:
            for id_ in filter_user_ids:
                filter_expressions.append(f'user_id in "{id_}"')

        query_expr = ' and '.join(filter_expressions) if filter_expressions else ''

        results = self.client.query(
            collection_name=f"document_info_{self.config.collection_name}",
            filter=query_expr,
            output_fields=["document_id", "title", "user_id",
                           "version", "size_in_bytes", "created_at",
                           "updated_at", "metadata"],
        )

        document_infos = []
        for row in results:
            document_info = DocumentInfo(
                document_id=uuid.UUID(row["document_id"]),
                title=row["title"],
                user_id=uuid.UUID(row["user_id"]) if row["user_id"] != "None" else None,
                version=row["version"],
                size_in_bytes=row["size_in_bytes"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=json.loads(row["metadata"]),
            )
            document_infos.append(document_info)

        return document_infos

    # TODO: Need future discussion of implementation
    def get_document_chunks(self, document_id: str) -> list[dict]:
        if not self.client.has_collection(
                collection_name=f"document_info_{self.config.collection_name}"
        ):
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `query`."
            )

        filter = f'document_id == "{document_id}"'

        results = self.client.query(
            collection_name=f"document_info_{self.config.collection_name}",
            filter=filter,
            output_fields=["metadata"],
        )

        # TODO: Need to check the metadata chunk key name
        document_chunks = [json.loads(result["metadata"])["chunk"] for result in results]
        document_chunks.sort(key=lambda x: x["chunk_order"])

        return document_chunks

    def delete_documents_info(self, document_ids: list[str]) -> None:
        if not self.client.has_collection(
                collection_name=f"document_info_{self.config.collection_name}"
        ):
            raise ValueError(
                "Please call `initialize_collection` before attempting to run `delete`."
            )

        for document_id in document_ids:
            filter_expression = f'document_id == "{document_id}"'

            try:
                self.client.delete(
                    collection_name=f"document_info_{self.config.collection_name}",
                    filter=filter_expression,
                )

            except Exception as e:
                raise ValueError(
                    f"Error {e} occurs in deletion of key value pair {self.config.collection_name}."
                )

    def get_users_stats(self, user_ids: Optional[list[str]] = None) -> list[UserStats]:
        # Construct filter expression
        filter_expression = ""
        if user_ids:
            user_ids_condition = ', '.join([f'"{str(user_id)}"' for user_id in user_ids])
            filter_expression = f"user_id in [{user_ids_condition}]"

        # Query Milvus
        try:
            results = self.client.query(
                collection_name=f"document_info_{self.config.collection_name}",
                expr=filter_expression,
                output_fields=["user_id", "document_id", "size_in_bytes"]
            )
        except Exception as e:
            raise ValueError(
                f"Error {e} occurs while query users stats."
            )

        # Process results
        user_stats = {}
        for result in results:
            user_id = result["user_id"]
            document_id = result["document_id"]
            size_in_bytes = result["size_in_bytes"]

            if user_id not in user_stats:
                user_stats[user_id] = {
                    "num_files": 0,
                    "total_size_in_bytes": 0,
                    "document_ids": []
                }

            user_stats[user_id]["num_files"] += 1
            user_stats[user_id]["total_size_in_bytes"] += size_in_bytes
            user_stats[user_id]["document_ids"].append(document_id)

        # Convert to UserStats objects
        user_stats_list = [
            UserStats(
                user_id=user_id,
                num_files=stats["num_files"],
                total_size_in_bytes=stats["total_size_in_bytes"],
                document_ids=stats["document_ids"]
            )
            for user_id, stats in user_stats.items()
        ]

        return user_stats_list

    # TODO: Need future discussion of implementation
    def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        limit: int = 10,
        filters: Optional[dict[str, Union[bool, int, str]]] = None,
        # Hybrid search parameters
        full_text_weight: float = 1.0,
        semantic_weight: float = 1.0,
        rrf_k: int = 20,  # typical value is ~2x the number of results you want
        *args,
        **kwargs,
    ) -> list[SearchResult]:
        pass