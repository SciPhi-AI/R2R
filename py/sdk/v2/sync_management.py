from __future__ import annotations  # for Python 3.10+

import json
from typing import Any, Optional, Union
from uuid import UUID

from typing_extensions import deprecated

from ..models import Message


class SyncManagementMixins:
    @deprecated("Use client.prompts.update() instead")
    def update_prompt(
        self,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = None,
    ) -> dict:
        """
        Update a prompt in the database.

        Args:
            name (str): The name of the prompt to update.
            template (Optional[str]): The new template for the prompt.
            input_types (Optional[dict[str, str]]): The new input types for the prompt.

        Returns:
            dict: The response from the server.
        """
        data: dict = {"name": name}
        if template is not None:
            data["template"] = template
        if input_types is not None:
            data["input_types"] = input_types

        return self._make_request("POST", "update_prompt", json=data)  # type: ignore

    @deprecated("Use client.prompts.create() instead")
    def add_prompt(
        self,
        name: str,
        template: str,
        input_types: dict[str, str],
    ) -> dict:
        """
        Add a new prompt to the system.

        Args:
            name (str): The name of the prompt.
            template (str): The template for the prompt.
            input_types (dict[str, str]): The input types for the prompt.

        Returns:
            dict: The response from the server.
        """
        data = {
            "name": name,
            "template": template,
            "input_types": input_types,
        }
        return self._make_request("POST", "add_prompt", json=data)  # type: ignore

    @deprecated("Use client.prompts.retrieve() instead")
    def get_prompt(
        self,
        prompt_name: str,
        inputs: Optional[dict[str, Any]] = None,
        prompt_override: Optional[str] = None,
    ) -> dict:
        """
        Get a prompt from the system.

        Args:
            prompt_name (str): The name of the prompt to retrieve.
            inputs (Optional[dict[str, Any]]): Optional inputs for the prompt.
            prompt_override (Optional[str]): Optional override for the prompt template.

        Returns:
            dict: The response from the server.
        """
        params = {}
        if inputs:
            params["inputs"] = json.dumps(inputs)
        if prompt_override:
            params["prompt_override"] = prompt_override
        return self._make_request(  # type: ignore
            "GET", f"get_prompt/{prompt_name}", params=params
        )

    @deprecated("Use client.prompts.list() instead")
    def get_all_prompts(self) -> dict:
        """
        Get all prompts from the system.

        Returns:
            dict: The response from the server containing all prompts.
        """
        return self._make_request("GET", "get_all_prompts")  # type: ignore

    @deprecated("Use client.prompts.delete() instead")
    def delete_prompt(self, prompt_name: str) -> dict:
        """
        Delete a prompt from the system.

        Args:
            prompt_name (str): The name of the prompt to delete.

        Returns:
            dict: The response from the server.
        """
        return self._make_request(  # type: ignore
            "DELETE", f"delete_prompt/{prompt_name}"
        )

    @deprecated(
        "This method is deprecated. New, improved analytics features will be added in a future release."
    )
    def analytics(
        self,
        filter_criteria: Optional[Union[dict, str]] = None,
        analysis_types: Optional[Union[dict, str]] = None,
    ) -> dict:
        """
        Get analytics data from the server.

        Args:
            filter_criteria (Optional[Union[dict, str]]): The filter criteria to use.
            analysis_types (Optional[Union[dict, str]]): The types of analysis to perform.

        Returns:
            dict: The analytics data from the server.
        """
        params = {}
        if filter_criteria:
            if isinstance(filter_criteria, dict):
                params["filter_criteria"] = json.dumps(filter_criteria)
            else:
                params["filter_criteria"] = filter_criteria
        if analysis_types:
            if isinstance(analysis_types, dict):
                params["analysis_types"] = json.dumps(analysis_types)
            else:
                params["analysis_types"] = analysis_types

        return self._make_request("GET", "analytics", params=params)  # type: ignore

    @deprecated("Use client.system.settings() instead")
    def app_settings(self) -> dict:
        """
        Get the configuration settings for the app.

        Returns:
            dict: The app settings.
        """
        return self._make_request("GET", "app_settings")  # type: ignore

    @deprecated("Use client.users.list() instead")
    def users_overview(
        self,
        user_ids: Optional[list[str]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        An overview of users in the R2R deployment.

        Args:
            user_ids (Optional[list[str]]): List of user IDs to get an overview for.

        Returns:
            dict: The overview of users in the system.
        """
        params: dict = {}
        if user_ids is not None:
            params["user_ids"] = [str(uid) for uid in user_ids]
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return self._make_request(  # type: ignore
            "GET", "users_overview", params=params
        )

    @deprecated("Use client.<object>.delete() instead")
    def delete(
        self,
        filters: dict,
    ) -> dict:
        """
        Delete data from the database given a set of filters.

        Args:
            filters (dict[str, str]): The filters to delete by.

        Returns:
            dict: The results of the deletion.
        """
        filters_json = json.dumps(filters)

        return self._make_request(  # type: ignore
            "DELETE", "delete", params={"filters": filters_json}
        ) or {"results": {}}

    @deprecated("Use client.documents.download() instead")
    def download_file(
        self,
        document_id: Union[str, UUID],
    ):
        """
        Download a file from the R2R deployment.

        Args:
            document_id (str): The ID of the document to download.

        Returns:
            dict: The response from the server.
        """
        return self._make_request(  # type: ignore
            "GET", f"download_file/{str(document_id)}"
        )

    @deprecated("Use client.documents.list() instead")
    def documents_overview(
        self,
        document_ids: Optional[list[Union[UUID, str]]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get an overview of documents in the R2R deployment.

        Args:
            document_ids (Optional[list[str]]): List of document IDs to get an overview for.

        Returns:
            dict: The overview of documents in the system.
        """
        params: dict = {}
        document_ids = (
            [str(doc_id) for doc_id in document_ids] if document_ids else None
        )
        if document_ids:
            params["document_ids"] = document_ids
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return self._make_request(  # type: ignore
            "GET", "documents_overview", params=params
        )

    @deprecated("Use client.documents.list_chunks() instead")
    def list_document_chunks(
        self,
        document_id: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        include_vectors: Optional[bool] = False,
    ) -> dict:
        """
        Get the chunks for a document.

        Args:
            document_id (str): The ID of the document to get chunks for.

        Returns:
            dict: The chunks for the document.
        """
        params: dict = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if include_vectors:
            params["include_vectors"] = include_vectors
        if not params:
            return self._make_request(  # type: ignore
                "GET", f"list_document_chunks/{document_id}"
            )
        else:
            return self._make_request(  # type: ignore
                "GET", f"list_document_chunks/{document_id}", params=params
            )

    @deprecated("Use client.collections.list() instead")
    def collections_overview(
        self,
        collection_ids: Optional[list[str]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get an overview of existing collections.

        Args:
            collection_ids (Optional[list[str]]): List of collection IDs to get an overview for.
            limit (Optional[int]): The maximum number of collections to return.
            offset (Optional[int]): The offset to start listing collections from.

        Returns:
            dict: The overview of collections in the system.
        """
        params: dict = {}
        if collection_ids:
            params["collection_ids"] = collection_ids
        if offset:
            params["offset"] = offset
        if limit:
            params["limit"] = limit
        return self._make_request(  # type: ignore
            "GET", "collections_overview", params=params
        )

    @deprecated("Use client.collections.create() instead")
    def create_collection(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> dict:
        """
        Create a new collection.

        Args:
            name (str): The name of the collection.
            description (Optional[str]): The description of the collection.

        Returns:
            dict: The response from the server.
        """
        data = {"name": name}
        if description is not None:
            data["description"] = description

        return self._make_request(  # type: ignore
            "POST", "create_collection", json=data
        )

    @deprecated("Use client.collections.retrieve() instead")
    def get_collection(
        self,
        collection_id: Union[str, UUID],
    ) -> dict:
        """
        Get a collection by its ID.

        Args:
            collection_id (str): The ID of the collection to get.

        Returns:
            dict: The collection data.
        """
        return self._make_request(  # type: ignore
            "GET", f"get_collection/{str(collection_id)}"
        )

    @deprecated("Use client.collections.update() instead")
    def update_collection(
        self,
        collection_id: Union[str, UUID],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        """
        Updates the name and description of a collection.

        Args:
            collection_id (str): The ID of the collection to update.
            name (Optional[str]): The new name for the collection.
            description (Optional[str]): The new description of the collection.

        Returns:
            dict: The response from the server.
        """
        data = {"collection_id": str(collection_id)}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        return self._make_request(  # type: ignore
            "PUT", "update_collection", json=data
        )

    @deprecated("Use client.collections.delete() instead")
    def delete_collection(
        self,
        collection_id: Union[str, UUID],
    ) -> dict:
        """
        Delete a collection by its ID.

        Args:
            collection_id (str): The ID of the collection to delete.

        Returns:
            dict: The response from the server.
        """
        return self._make_request(  # type: ignore
            "DELETE", f"delete_collection/{str(collection_id)}"
        )

    @deprecated("Use client.users.delete() instead")
    def delete_user(
        self,
        user_id: str,
        password: Optional[str] = None,
        delete_vector_data: bool = False,
    ) -> dict:
        """
        Delete a collection by its ID.

        Args:
            collection_id (str): The ID of the collection to delete.

        Returns:
            dict: The response from the server.
        """
        params: dict = {}
        if password is not None:
            params["password"] = password
        if delete_vector_data:
            params["delete_vector_data"] = delete_vector_data
        if not params:
            return self._make_request("DELETE", f"user/{user_id}")  # type: ignore
        else:
            return self._make_request(  # type: ignore
                "DELETE", f"user/{user_id}", json=params
            )

    @deprecated("Use client.collections.list() instead")
    def list_collections(
        self,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        List all collections in the R2R deployment.

        Args:
            offset (Optional[int]): The offset to start listing collections from.
            limit (Optional[int]): The maximum number of collections to return.

        Returns:
            dict: The list of collections.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return self._make_request(  # type: ignore
            "GET", "list_collections", params=params
        )

    @deprecated("Use client.collections.add_user() instead")
    def add_user_to_collection(
        self,
        user_id: Union[str, UUID],
        collection_id: Union[str, UUID],
    ) -> dict:
        """
        Add a user to a collection.

        Args:
            user_id (str): The ID of the user to add.
            collection_id (str): The ID of the collection to add the user to.

        Returns:
            dict: The response from the server.
        """
        data = {
            "user_id": str(user_id),
            "collection_id": str(collection_id),
        }
        return self._make_request(  # type: ignore
            "POST", "add_user_to_collection", json=data
        )

    @deprecated("Use client.collections.remove_user() instead")
    def remove_user_from_collection(
        self,
        user_id: Union[str, UUID],
        collection_id: Union[str, UUID],
    ) -> dict:
        """
        Remove a user from a collection.

        Args:
            user_id (str): The ID of the user to remove.
            collection_id (str): The ID of the collection to remove the user from.

        Returns:
            dict: The response from the server.
        """
        data = {
            "user_id": str(user_id),
            "collection_id": str(collection_id),
        }
        return self._make_request(  # type: ignore
            "POST", "remove_user_from_collection", json=data
        )

    @deprecated("Use client.collections.list_users() instead")
    def get_users_in_collection(
        self,
        collection_id: Union[str, UUID],
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get all users in a collection.

        Args:
            collection_id (str): The ID of the collection to get users for.
            offset (Optional[int]): The offset to start listing users from.
            limit (Optional[int]): The maximum number of users to return.

        Returns:
            dict: The list of users in the collection.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return self._make_request(  # type: ignore
            "GET",
            f"get_users_in_collection/{str(collection_id)}",
            params=params,
        )

    @deprecated("Use client.users.list_collections() instead")
    def user_collections(
        self,
        user_id: Union[str, UUID],
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get all collections that a user is a member of.

        Args:
            user_id (str): The ID of the user to get collections for.

        Returns:
            dict: The list of collections that the user is a member of.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if not params:
            return self._make_request(  # type: ignore
                "GET", f"user_collections/{str(user_id)}"
            )
        else:
            return self._make_request(  # type: ignore
                "GET", f"user_collections/{str(user_id)}", params=params
            )

    @deprecated("Use client.collections.add_document() instead")
    def assign_document_to_collection(
        self,
        document_id: Union[str, UUID],
        collection_id: Union[str, UUID],
    ) -> dict:
        """
        Assign a document to a collection.

        Args:
            document_id (str): The ID of the document to assign.
            collection_id (str): The ID of the collection to assign the document to.

        Returns:
            dict: The response from the server.
        """
        data = {
            "document_id": str(document_id),
            "collection_id": str(collection_id),
        }
        return self._make_request(  # type: ignore
            "POST", "assign_document_to_collection", json=data
        )

    # TODO: Verify that this method is implemented, also, should be a PUT request
    @deprecated("Use client.collections.remove_document() instead")
    def remove_document_from_collection(
        self,
        document_id: Union[str, UUID],
        collection_id: Union[str, UUID],
    ) -> dict:
        """
        Remove a document from a collection.

        Args:
            document_id (str): The ID of the document to remove.
            collection_id (str): The ID of the collection to remove the document from.

        Returns:
            dict: The response from the server.
        """
        data = {
            "document_id": str(document_id),
            "collection_id": str(collection_id),
        }
        return self._make_request(  # type: ignore
            "POST", "remove_document_from_collection", json=data
        )

    @deprecated("Use client.documents.list_collections() instead")
    def document_collections(
        self,
        document_id: Union[str, UUID],
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get all collections that a document is assigned to.

        Args:
            document_id (str): The ID of the document to get collections for.

        Returns:
            dict: The list of collections that the document is assigned to.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if not params:
            return self._make_request(  # type: ignore
                "GET",
                f"document_collections/{str(document_id)}",
                params=params,
            )
        else:
            return self._make_request(  # type: ignore
                "GET", f"document_collections/{str(document_id)}"
            )

    @deprecated("Use client.collections.list_documents() instead")
    def documents_in_collection(
        self,
        collection_id: Union[str, UUID],
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get all documents in a collection.

        Args:
            collection_id (str): The ID of the collection to get documents for.
            offset (Optional[int]): The offset to start listing documents from.
            limit (Optional[int]): The maximum number of documents to return.

        Returns:
            dict: The list of documents in the collection.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return self._make_request(  # type: ignore
            "GET", f"collection/{str(collection_id)}/documents", params=params
        )

    @deprecated("Use client.conversations.list() instead")
    def conversations_overview(
        self,
        conversation_ids: Optional[list[Union[UUID, str]]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get an overview of existing conversations.

        Args:
            conversation_ids (Optional[list[Union[UUID, str]]]): list of conversation IDs to retrieve.
            offset (Optional[int]): The offset to start listing conversations from.
            limit (Optional[int]): The maximum number of conversations to return.

        Returns:
            dict[str, any]: The overview of conversations in the system.
        """
        params: dict = {}
        if conversation_ids:
            params["conversation_ids"] = [str(cid) for cid in conversation_ids]
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return self._make_request(  # type: ignore
            "GET", "conversations_overview", params=params
        )

    @deprecated("Use client.conversations.retrieve() instead")
    def get_conversation(
        self,
        conversation_id: Union[str, UUID],
        branch_id: Optional[str] = None,
    ) -> dict:
        """
        Get a conversation by its ID.

        Args:
            conversation_id (Union[str, UUID]): The ID of the conversation to retrieve.
            branch_id (Optional[str]): The ID of a specific branch to retrieve.

        Returns:
            dict: The conversation data.
        """
        query_params = f"?branch_id={branch_id}" if branch_id else ""
        return self._make_request(  # type: ignore
            "GET", f"get_conversation/{str(conversation_id)}{query_params}"
        )

    @deprecated("Use client.conversations.create() instead")
    def create_conversation(self) -> dict:
        """
        Create a new conversation.

        Returns:
            dict: The response from the server.
        """
        return self._make_request("POST", "create_conversation")  # type: ignore

    @deprecated("Use client.conversations.add_message() instead")
    def add_message(
        self,
        conversation_id: Union[str, UUID],
        message: Message,
        parent_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict:
        """
        Add a message to an existing conversation.

        Args:
            conversation_id (Union[str, UUID]): The ID of the conversation.
            message (Message): The message to add.
            parent_id (Optional[str]): The ID of the parent message.
            metadata (Optional[dict[str, Any]]): Additional metadata for the message.

        Returns:
            dict: The response from the server.
        """
        data: dict = {"message": message}
        if parent_id is not None:
            data["parent_id"] = parent_id
        if metadata is not None:
            data["metadata"] = metadata
        return self._make_request(  # type: ignore
            "POST", f"add_message/{str(conversation_id)}", data=data
        )

    @deprecated("Use client.conversations.update_message() instead")
    def update_message(
        self,
        message_id: str,
        message: Message,
    ) -> dict:
        """
        Update a message in an existing conversation.

        Args:
            message_id (str): The ID of the message to update.
            message (Message): The updated message.

        Returns:
            dict: The response from the server.
        """
        return self._make_request(  # type: ignore
            "PUT", f"update_message/{message_id}", data=message
        )

    def update_message_metadata(
        self,
        message_id: str,
        metadata: dict[str, Any],
    ) -> dict:
        """
        Update the metadata of a message.

        Args:
            message_id (str): The ID of the message to update.
            metadata (dict[str, Any]): The metadata to update.

        Returns:
            dict: The response from the server.
        """
        return self._make_request(  # type: ignore
            "PATCH", f"messages/{message_id}/metadata", data=metadata
        )

    @deprecated("Use client.conversations.list_branches() instead")
    def branches_overview(
        self,
        conversation_id: Union[str, UUID],
    ) -> dict:
        """
        Get an overview of branches in a conversation.

        Args:
            conversation_id (Union[str, UUID]): The ID of the conversation to get branches for.

        Returns:
            dict: The response from the server.
        """
        return self._make_request(  # type: ignore
            "GET", f"branches_overview/{str(conversation_id)}"
        )

    @deprecated("Use client.conversations.delete() instead")
    def delete_conversation(
        self,
        conversation_id: Union[str, UUID],
    ) -> dict:
        """
        Delete a conversation by its ID.

        Args:
            conversation_id (Union[str, UUID]): The ID of the conversation to delete.

        Returns:
            dict: The response from the server.
        """
        return self._make_request(  # type: ignore
            "DELETE", f"delete_conversation/{str(conversation_id)}"
        )
