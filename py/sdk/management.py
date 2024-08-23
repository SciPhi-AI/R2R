import json
from typing import Optional, Union
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
        data = {name: name}
        if template is not None:
            data["template"] = template
        if input_types is not None:
            data["input_types"] = input_types

        return await client._make_request("POST", "update_prompt", json=data)

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
        params = {}
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
        params = {}
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
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if params:
            return await client._make_request(
                "GET", f"document_chunks/{document_id}"
            )
        else:
            return await client._make_request(
                "GET", f"document_chunks/{document_id}", params=params
            )

    @staticmethod
    async def inspect_knowledge_graph(
        client,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Inspect the knowledge graph associated with your R2R deployment.

        Args:
            limit (Optional[int]): The maximum number of nodes to return. Defaults to 100.

        Returns:
            dict: The knowledge graph inspection results.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return await client._make_request(
            "GET", "inspect_knowledge_graph", params=params
        )

    @staticmethod
    async def groups_overview(
        client,
        group_ids: Optional[list[str]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get an overview of existing groups.

        Args:
            group_ids (Optional[list[str]]): List of group IDs to get an overview for.
            limit (Optional[int]): The maximum number of groups to return.
            offset (Optional[int]): The offset to start listing groups from.

        Returns:
            dict: The overview of groups in the system.
        """
        params = {}
        if group_ids:
            params["group_ids"] = group_ids
        if offset:
            params["offset"] = offset
        if limit:
            params["limit"] = limit
        return await client._make_request(
            "GET", "groups_overview", params=params
        )

    @staticmethod
    async def create_group(
        client,
        name: str,
        description: Optional[str] = None,
    ) -> dict:
        """
        Create a new group.

        Args:
            name (str): The name of the group.
            description (Optional[str]): The description of the group.

        Returns:
            dict: The response from the server.
        """
        data = {"name": name}
        if description is not None:
            data["description"] = description

        return await client._make_request("POST", "create_group", json=data)

    @staticmethod
    async def get_group(
        client,
        group_id: Union[str, UUID],
    ) -> dict:
        """
        Get a group by its ID.

        Args:
            group_id (str): The ID of the group to get.

        Returns:
            dict: The group data.
        """
        return await client._make_request("GET", f"get_group/{str(group_id)}")

    @staticmethod
    async def update_group(
        client,
        group_id: Union[str, UUID],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        """
        Updates the name and description of a group.

        Args:
            group_id (str): The ID of the group to update.
            name (Optional[str]): The new name for the group.
            description (Optional[str]): The new description of the group.

        Returns:
            dict: The response from the server.
        """
        data = {"group_id": str(group_id)}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        return await client._make_request("PUT", "update_group", json=data)

    @staticmethod
    async def delete_group(
        client,
        group_id: Union[str, UUID],
    ) -> dict:
        """
        Delete a group by its ID.

        Args:
            group_id (str): The ID of the group to delete.

        Returns:
            dict: The response from the server.
        """
        return await client._make_request(
            "DELETE", f"delete_group/{str(group_id)}"
        )

    @staticmethod
    async def delete_user(
        client,
        user_id: str,
        password: Optional[str] = None,
        delete_vector_data: bool = False,
    ) -> dict:
        """
        Delete a group by its ID.

        Args:
            group_id (str): The ID of the group to delete.

        Returns:
            dict: The response from the server.
        """
        params = {}
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
    async def list_groups(
        client,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        List all groups in the R2R deployment.

        Args:
            offset (Optional[int]): The offset to start listing groups from.
            limit (Optional[int]): The maximum number of groups to return.

        Returns:
            dict: The list of groups.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return await client._make_request("GET", "list_groups", params=params)

    @staticmethod
    async def add_user_to_group(
        client,
        user_id: Union[str, UUID],
        group_id: Union[str, UUID],
    ) -> dict:
        """
        Add a user to a group.

        Args:
            user_id (str): The ID of the user to add.
            group_id (str): The ID of the group to add the user to.

        Returns:
            dict: The response from the server.
        """
        data = {
            "user_id": str(user_id),
            "group_id": str(group_id),
        }
        return await client._make_request(
            "POST", "add_user_to_group", json=data
        )

    @staticmethod
    async def remove_user_from_group(
        client,
        user_id: Union[str, UUID],
        group_id: Union[str, UUID],
    ) -> dict:
        """
        Remove a user from a group.

        Args:
            user_id (str): The ID of the user to remove.
            group_id (str): The ID of the group to remove the user from.

        Returns:
            dict: The response from the server.
        """
        data = {
            "user_id": str(user_id),
            "group_id": str(group_id),
        }
        return await client._make_request(
            "POST", "remove_user_from_group", json=data
        )

    @staticmethod
    async def get_users_in_group(
        client,
        group_id: Union[str, UUID],
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get all users in a group.

        Args:
            group_id (str): The ID of the group to get users for.
            offset (Optional[int]): The offset to start listing users from.
            limit (Optional[int]): The maximum number of users to return.

        Returns:
            dict: The list of users in the group.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return await client._make_request(
            "GET", f"get_users_in_group/{str(group_id)}", params=params
        )

    @staticmethod
    async def user_groups(
        client,
        user_id: Union[str, UUID],
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get all groups that a user is a member of.

        Args:
            user_id (str): The ID of the user to get groups for.

        Returns:
            dict: The list of groups that the user is a member of.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if params:
            return await client._make_request(
                "GET", f"user_groups/{str(user_id)}"
            )
        else:
            return await client._make_request(
                "GET", f"user_groups/{str(user_id)}", params=params
            )

    @staticmethod
    async def assign_document_to_group(
        client,
        document_id: Union[str, UUID],
        group_id: Union[str, UUID],
    ) -> dict:
        """
        Assign a document to a group.

        Args:
            document_id (str): The ID of the document to assign.
            group_id (str): The ID of the group to assign the document to.

        Returns:
            dict: The response from the server.
        """
        data = {
            "document_id": str(document_id),
            "group_id": str(group_id),
        }
        return await client._make_request(
            "POST", "assign_document_to_group", json=data
        )

    # TODO: Verify that this method is implemented, also, should be a PUT request
    @staticmethod
    async def remove_document_from_group(
        client,
        document_id: Union[str, UUID],
        group_id: Union[str, UUID],
    ) -> dict:
        """
        Remove a document from a group.

        Args:
            document_id (str): The ID of the document to remove.
            group_id (str): The ID of the group to remove the document from.

        Returns:
            dict: The response from the server.
        """
        data = {
            "document_id": str(document_id),
            "group_id": str(group_id),
        }
        return await client._make_request(
            "POST", "remove_document_from_group", json=data
        )

    @staticmethod
    async def document_groups(
        client,
        document_id: Union[str, UUID],
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get all groups that a document is assigned to.

        Args:
            document_id (str): The ID of the document to get groups for.

        Returns:
            dict: The list of groups that the document is assigned to.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        if params:
            return await client._make_request(
                "GET", f"document_groups/{str(document_id)}", params=params
            )
        else:
            return await client._make_request(
                "GET", f"document_groups/{str(document_id)}"
            )

    @staticmethod
    async def documents_in_group(
        client,
        group_id: Union[str, UUID],
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Get all documents in a group.

        Args:
            group_id (str): The ID of the group to get documents for.
            offset (Optional[int]): The offset to start listing documents from.
            limit (Optional[int]): The maximum number of documents to return.

        Returns:
            dict: The list of documents in the group.
        """
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return await client._make_request(
            "GET", f"group/{str(group_id)}/documents", params=params
        )
