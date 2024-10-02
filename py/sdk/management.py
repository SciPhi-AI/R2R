import json
from typing import Any, Optional, Union
from uuid import UUID


class ManagementMethods:
    @staticmethod
    async def update_prompt(
        client,
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
        data: dict = {name: name}
        if template is not None:
            data["template"] = template
        if input_types is not None:
            data["input_types"] = input_types

        return await client._make_request("POST", "update_prompt", json=data)

    @staticmethod
    async def add_prompt(
        client,
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
        return await client._make_request("POST", "add_prompt", json=data)

    @staticmethod
    async def get_prompt(
        client,
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
        return await client._make_request(
            "GET", f"get_prompt/{prompt_name}", params=params
        )

    @staticmethod
    async def get_all_prompts(client) -> dict:
        """
        Get all prompts from the system.

        Returns:
            dict: The response from the server containing all prompts.
        """
        return await client._make_request("GET", "get_all_prompts")

    @staticmethod
    async def delete_prompt(client, prompt_name: str) -> dict:
        """
        Delete a prompt from the system.

        Args:
            prompt_name (str): The name of the prompt to delete.

        Returns:
            dict: The response from the server.
        """
        return await client._make_request(
            "DELETE", f"delete_prompt/{prompt_name}"
        )

    @staticmethod
    async def analytics(
        client,
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

        return await client._make_request("GET", "analytics", params=params)

    @staticmethod
    async def app_settings(client) -> dict:
        """
        Get the configuration settings for the app.

        Returns:
            dict: The app settings.
        """
        return await client._make_request("GET", "app_settings")

    @staticmethod
    async def score_completion(
        client,
        message_id: str,
        score: float = 0.0,
    ) -> dict:
        """
        Assign a score to a message from an LLM completion. The score should be a float between -1.0 and 1.0.

        Args:
            message_id (str): The ID of the message to score.
            score (float): The score to assign to the message.

        Returns:
            dict: The response from the server.
        """
        data = {"message_id": message_id, "score": score}
        return await client._make_request(
            "POST", "score_completion", json=data
        )

    @staticmethod
    async def users_overview(
        client,
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
        return await client._make_request(
            "GET", "users_overview", params=params
        )

    @staticmethod
    async def delete(
        client,
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

        return await client._make_request(
            "DELETE", "delete", params={"filters": filters_json}
        ) or {"results": {}}

    @staticmethod
    async def download_file(
        client,
        document_id: Union[str, UUID],
    ):
        """
        Download a file from the R2R deployment.

        Args:
            document_id (str): The ID of the document to download.

        Returns:
            dict: The response from the server.
        """
        return await client._make_request(
            "GET", f"download_file/{str(document_id)}"
        )

    @staticmethod
    async def documents_overview(
        client,
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
        return await client._make_request(
            "GET", "documents_overview", params=params
        )

    @staticmethod
    async def document_chunks(
        client,
        document_id: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
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
        if not params:
            return await client._make_request(
                "GET", f"document_chunks/{document_id}"
            )
        else:
            return await client._make_request(
                "GET", f"document_chunks/{document_id}", params=params
            )

    @staticmethod
    async def collections_overview(
        client,
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
        return await client._make_request(
            "GET", "collections_overview", params=params
        )

    @staticmethod
    async def create_collection(
        client,
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

        return await client._make_request(
            "POST", "create_collection", json=data
        )

    @staticmethod
    async def get_collection(
        client,
        collection_id: Union[str, UUID],
    ) -> dict:
        """
        Get a collection by its ID.

        Args:
            collection_id (str): The ID of the collection to get.

        Returns:
            dict: The collection data.
        """
        return await client._make_request(
            "GET", f"get_collection/{str(collection_id)}"
        )

    @staticmethod
    async def update_collection(
        client,
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

        return await client._make_request(
            "PUT", "update_collection", json=data
        )

    @staticmethod
    async def delete_collection(
        client,
        collection_id: Union[str, UUID],
    ) -> dict:
        """
        Delete a collection by its ID.

        Args:
            collection_id (str): The ID of the collection to delete.

        Returns:
            dict: The response from the server.
        """
        return await client._make_request(
            "DELETE", f"delete_collection/{str(collection_id)}"
        )

    @staticmethod
    async def delete_user(
        client,
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
        if params == {}:
            return await client._make_request("DELETE", f"user/{user_id}")
        else:
            return await client._make_request(
                "DELETE", f"user/{user_id}", json=params
            )

    @staticmethod
    async def list_collections(
        client,
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
        return await client._make_request(
            "GET", "list_collections", params=params
        )

    @staticmethod
    async def add_user_to_collection(
        client,
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
        return await client._make_request(
            "POST", "add_user_to_collection", json=data
        )

    @staticmethod
    async def remove_user_from_collection(
        client,
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
        return await client._make_request(
            "POST", "remove_user_from_collection", json=data
        )

    @staticmethod
    async def get_users_in_collection(
        client,
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
        return await client._make_request(
            "GET",
            f"get_users_in_collection/{str(collection_id)}",
            params=params,
        )

    @staticmethod
    async def user_collections(
        client,
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
            return await client._make_request(
                "GET", f"user_collections/{str(user_id)}"
            )
        else:
            return await client._make_request(
                "GET", f"user_collections/{str(user_id)}", params=params
            )

    @staticmethod
    async def assign_document_to_collection(
        client,
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
        return await client._make_request(
            "POST", "assign_document_to_collection", json=data
        )

    # TODO: Verify that this method is implemented, also, should be a PUT request
    @staticmethod
    async def remove_document_from_collection(
        client,
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
        return await client._make_request(
            "POST", "remove_document_from_collection", json=data
        )

    @staticmethod
    async def document_collections(
        client,
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
            return await client._make_request(
                "GET",
                f"document_collections/{str(document_id)}",
                params=params,
            )
        else:
            return await client._make_request(
                "GET", f"document_collections/{str(document_id)}"
            )

    @staticmethod
    async def documents_in_collection(
        client,
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
        return await client._make_request(
            "GET", f"collection/{str(collection_id)}/documents", params=params
        )
