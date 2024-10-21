import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Union, Sequence

from pydantic import BaseModel
from uuid import UUID
from shared.abstractions.vector import VectorQuantizationType

from .base import Provider, ProviderConfig

logger = logging.getLogger()


class PostgresConfigurationSettings(BaseModel):
    """
    Configuration settings with defaults defined by the PGVector docker image.

    These settings are helpful in managing the connections to the database.
    To tune these settings for a specific deployment, see https://pgtune.leopard.in.ua/
    """

    max_connections: Optional[int] = 256
    shared_buffers: Optional[int] = 16384
    effective_cache_size: Optional[int] = 524288
    maintenance_work_mem: Optional[int] = 65536
    checkpoint_completion_target: Optional[float] = 0.9
    wal_buffers: Optional[int] = 512
    default_statistics_target: Optional[int] = 100
    random_page_cost: Optional[float] = 4
    effective_io_concurrency: Optional[int] = 1
    work_mem: Optional[int] = 4096
    huge_pages: Optional[str] = "try"
    min_wal_size: Optional[int] = 80
    max_wal_size: Optional[int] = 1024
    max_worker_processes: Optional[int] = 8
    max_parallel_workers_per_gather: Optional[int] = 2
    max_parallel_workers: Optional[int] = 8
    max_parallel_maintenance_workers: Optional[int] = 2


class DatabaseConfig(ProviderConfig):
    """A base database configuration class"""

    provider: str = "postgres"
    user: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    db_name: Optional[str] = None
    project_name: Optional[str] = None
    postgres_configuration_settings: Optional[
        PostgresConfigurationSettings
    ] = None
    default_collection_name: str = "Default"
    default_collection_description: str = "Your default collection."
    enable_fts: bool = False

    def __post_init__(self):
        self.validate_config()
        # Capture additional fields
        for key, value in self.extra_fields.items():
            setattr(self, key, value)

    def validate_config(self) -> None:
        if self.provider not in self.supported_providers:
            raise ValueError(f"Provider '{self.provider}' is not supported.")

    @property
    def supported_providers(self) -> list[str]:
        return ["postgres"]


class DatabaseProvider(Provider):
    def __init__(self, config: DatabaseConfig):
        logger.info(f"Initializing DatabaseProvider with config {config}.")

        super().__init__(config)

    @abstractmethod
    def _get_table_name(self, base_name: str) -> str:
        pass
    
    @abstractmethod
    def execute_query(
        self,
        query: str,
        params: Optional[Union[dict[str, Any], Sequence[Any]]] = None,
        isolation_level: Optional[str] = None,
    ):
        pass

    @abstractmethod
    async def execute_many(self, query, params=None, batch_size=1000):
        pass

    @abstractmethod
    def fetch_query(
        self,
        query: str,
        params: Optional[Union[dict[str, Any], Sequence[Any]]] = None,
    ):
        pass

    @abstractmethod
    def fetchrow_query(
        self,
        query: str,
        params: Optional[Union[dict[str, Any], Sequence[Any]]] = None,
    ):
        pass

    # @abstractmethod
    # def create_table(self):
    #     pass

    # # Management Methods
    # @abstractmethod
    # async def update_prompt(
    #     self,
    #     name: str,
    #     template: Optional[str] = None,
    #     input_types: Optional[dict[str, str]] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def add_prompt(
    #     self,
    #     name: str,
    #     template: str,
    #     input_types: dict[str, str],
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def get_prompt(
    #     self,
    #     prompt_name: str,
    #     inputs: Optional[dict[str, Any]] = None,
    #     prompt_override: Optional[str] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def get_all_prompts(self) -> dict:
    #     pass

    # @abstractmethod
    # async def delete_prompt(self, prompt_name: str) -> dict:
    #     pass

    # @abstractmethod
    # async def analytics(
    #     self,
    #     filter_criteria: Optional[Union[dict, str]] = None,
    #     analysis_types: Optional[Union[dict, str]] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def app_settings(self) -> dict:
    #     pass

    # @abstractmethod
    # async def users_overview(
    #     self,
    #     user_ids: Optional[list[str]] = None,
    #     offset: Optional[int] = None,
    #     limit: Optional[int] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def delete(
    #     self,
    #     filters: dict,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def download_file(
    #     self,
    #     document_id: Union[str, UUID],
    # ):
    #     pass

    # @abstractmethod
    # async def documents_overview(
    #     self,
    #     document_ids: Optional[list[Union[UUID, str]]] = None,
    #     offset: Optional[int] = None,
    #     limit: Optional[int] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def document_chunks(
    #     self,
    #     document_id: str,
    #     offset: Optional[int] = None,
    #     limit: Optional[int] = None,
    #     include_vectors: Optional[bool] = False,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def collections_overview(
    #     self,
    #     collection_ids: Optional[list[str]] = None,
    #     offset: Optional[int] = None,
    #     limit: Optional[int] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def create_collection(
    #     self,
    #     name: str,
    #     description: Optional[str] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def get_collection(
    #     self,
    #     collection_id: Union[str, UUID],
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def update_collection(
    #     self,
    #     collection_id: Union[str, UUID],
    #     name: Optional[str] = None,
    #     description: Optional[str] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def delete_collection(
    #     self,
    #     collection_id: Union[str, UUID],
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def delete_user(
    #     self,
    #     user_id: str,
    #     password: Optional[str] = None,
    #     delete_vector_data: bool = False,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def list_collections(
    #     self,
    #     offset: Optional[int] = None,
    #     limit: Optional[int] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def add_user_to_collection(
    #     self,
    #     user_id: Union[str, UUID],
    #     collection_id: Union[str, UUID],
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def remove_user_from_collection(
    #     self,
    #     user_id: Union[str, UUID],
    #     collection_id: Union[str, UUID],
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def get_users_in_collection(
    #     self,
    #     collection_id: Union[str, UUID],
    #     offset: Optional[int] = None,
    #     limit: Optional[int] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def user_collections(
    #     self,
    #     user_id: Union[str, UUID],
    #     offset: Optional[int] = None,
    #     limit: Optional[int] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def assign_document_to_collection(
    #     self,
    #     document_id: Union[str, UUID],
    #     collection_id: Union[str, UUID],
    # ) -> dict:
    #     pass


    # # TODO: Verify that this method is implemented, also, should be a PUT request
    # @abstractmethod
    # async def remove_document_from_collection(
    #     self,
    #     document_id: Union[str, UUID],
    #     collection_id: Union[str, UUID],
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def document_collections(
    #     self,
    #     document_id: Union[str, UUID],
    #     offset: Optional[int] = None,
    #     limit: Optional[int] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def documents_in_collection(
    #     self,
    #     collection_id: Union[str, UUID],
    #     offset: Optional[int] = None,
    #     limit: Optional[int] = None,
    # ) -> dict:
    #     pass

    # @abstractmethod
    # async def conversations_overview(
    #     self,
    #     conversation_ids: Optional[list[Union[UUID, str]]] = None,
    #     offset: Optional[int] = None,
    #     limit: Optional[int] = None,
    # ) -> dict:
    #     pass

    # # async def get_conversation(
    # #     self,
    # #     conversation_id: Union[str, UUID],
    # #     branch_id: Optional[str] = None,
    # # ) -> dict:
    # #     """
    # #     Get a conversation by its ID.

    # #     Args:
    # #         conversation_id (Union[str, UUID]): The ID of the conversation to retrieve.
    # #         branch_id (Optional[str]): The ID of a specific branch to retrieve.

    # #     Returns:
    # #         dict: The conversation data.
    # #     """
    # #     query_params = f"?branch_id={branch_id}" if branch_id else ""
    # #     return await self._make_request(  # type: ignore
    # #         "GET", f"get_conversation/{str(conversation_id)}{query_params}"
    # #     )

    # # async def create_conversation(self) -> dict:
    # #     """
    # #     Create a new conversation.

    # #     Returns:
    # #         dict: The response from the server.
    # #     """
    # #     return await self._make_request("POST", "create_conversation")  # type: ignore

    # # async def add_message(
    # #     self,
    # #     conversation_id: Union[str, UUID],
    # #     message: Message,
    # #     parent_id: Optional[str] = None,
    # #     metadata: Optional[dict[str, Any]] = None,
    # # ) -> dict:
    # #     """
    # #     Add a message to an existing conversation.

    # #     Args:
    # #         conversation_id (Union[str, UUID]): The ID of the conversation.
    # #         message (Message): The message to add.
    # #         parent_id (Optional[str]): The ID of the parent message.
    # #         metadata (Optional[dict[str, Any]]): Additional metadata for the message.

    # #     Returns:
    # #         dict: The response from the server.
    # #     """
    # #     data: dict = {"message": message}
    # #     if parent_id is not None:
    # #         data["parent_id"] = parent_id
    # #     if metadata is not None:
    # #         data["metadata"] = metadata
    # #     return await self._make_request(  # type: ignore
    # #         "POST", f"add_message/{str(conversation_id)}", data=data
    # #     )

    # # async def update_message(
    # #     self,
    # #     message_id: str,
    # #     message: Message,
    # # ) -> dict:
    # #     """
    # #     Update a message in an existing conversation.

    # #     Args:
    # #         message_id (str): The ID of the message to update.
    # #         message (Message): The updated message.

    # #     Returns:
    # #         dict: The response from the server.
    # #     """
    # #     return await self._make_request(  # type: ignore
    # #         "PUT", f"update_message/{message_id}", data=message
    # #     )

    # # async def branches_overview(
    # #     self,
    # #     conversation_id: Union[str, UUID],
    # # ) -> dict:
    # #     """
    # #     Get an overview of branches in a conversation.

    # #     Args:
    # #         conversation_id (Union[str, UUID]): The ID of the conversation to get branches for.

    # #     Returns:
    # #         dict: The response from the server.
    # #     """
    # #     return await self._make_request(  # type: ignore
    # #         "GET", f"branches_overview/{str(conversation_id)}"
    # #     )

    # # async def delete_conversation(
    # #     self,
    # #     conversation_id: Union[str, UUID],
    # # ) -> dict:
    # #     """
    # #     Delete a conversation by its ID.

    # #     Args:
    # #         conversation_id (Union[str, UUID]): The ID of the conversation to delete.

    # #     Returns:
    # #         dict: The response from the server.
    # #     """
    # #     return await self._make_request(  # type: ignore
    # #         "DELETE", f"delete_conversation/{str(conversation_id)}"
    # #     )
