import json
from typing import Optional, Union


class ManagementMethods:
    @staticmethod
    async def server_stats(client) -> dict:
        return await client._make_request("GET", "server_stats")

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
            name (str): The name of the prompt.
            template (Optional[str]): The template to use for the prompt.
            input_types (Optional[dict[str, str]]): The input types for the prompt.

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
    async def logs(
        client,
        run_type_filter: Optional[str] = None,
        max_runs: int = None,
    ) -> dict:
        params = {}
        if run_type_filter is not None:
            params["run_type_filter"] = run_type_filter
        if max_runs is not None:
            params["max_runs"] = max_runs
        return await client._make_request("GET", "logs", params=params)

    @staticmethod
    async def app_settings(client) -> dict:
        return await client._make_request("GET", "app_settings")

    @staticmethod
    async def score_completion(
        client,
        message_id: str,
        score: float = 0.0,
    ) -> dict:
        data = {"message_id": message_id, "score": score}
        return await client._make_request(
            "POST", "score_completion", json=data
        )

    @staticmethod
    async def users_overview(
        client,
        user_ids: Optional[list[str]] = None,
    ) -> dict:
        params = {
            "user_ids": [str(uid) for uid in user_ids] if user_ids else None
        }
        return await client._make_request(
            "GET", "users_overview", params=params
        )

    @staticmethod
    async def delete(
        client,
        filters: dict[str, str],
    ) -> dict:
        filters_json = json.dumps(filters)

        return await client._make_request(
            "DELETE", "delete", params={"filters": filters_json}
        ) or {"results": {}}

    @staticmethod
    async def documents_overview(
        client,
        document_ids: Optional[list[str]] = None,
    ) -> dict:
        params = {}
        if document_ids:
            params["document_ids"] = document_ids

        return await client._make_request(
            "GET", "documents_overview", params=params
        )

    @staticmethod
    async def document_chunks(
        client,
        document_id: str,
    ) -> dict:
        return await client._make_request(
            "GET", "document_chunks", params={"document_id": document_id}
        )

    @staticmethod
    async def inspect_knowledge_graph(
        client,
        limit: Optional[int] = None,
    ) -> dict:
        params = {}
        if limit is not None:
            params["limit"] = limit
        return await client._make_request(
            "GET", "inspect_knowledge_graph", params=params
        )

    @staticmethod
    async def assign_document_to_group(
        client,
        document_id: str,
        group_id: str,
    ) -> dict:
        data = {
            "document_id": document_id,
            "group_id": group_id,
        }
        return await client._make_request(
            "POST", "assign_document_to_group", json=data
        )

    # TODO: Verify that this method is implemented, also, should be a PUT request
    @staticmethod
    async def remove_document_from_group(
        client,
        document_id: str,
        group_id: str,
    ) -> dict:
        data = {
            "document_id": document_id,
            "group_id": group_id,
        }
        return await client._make_request(
            "POST", "remove_document_from_group", json=data
        )

    @staticmethod
    async def get_document_groups(
        client,
        document_id: str,
    ) -> dict:
        return await client._make_request(
            "GET", f"get_document_groups/{document_id}"
        )

    @staticmethod
    async def create_group(
        client,
        name: str,
        description: Optional[str] = None,
    ) -> dict:
        data = {"name": name}
        if description is not None:
            data["description"] = description

        return await client._make_request("POST", "create_group", json=data)

    @staticmethod
    async def get_group(
        client,
        group_id: str,
    ) -> dict:
        return await client._make_request("GET", f"get_group/{group_id}")

    @staticmethod
    async def update_group(
        client,
        group_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        data = {"group_id": group_id}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        return await client._make_request("PUT", "update_group", json=data)

    @staticmethod
    async def delete_group(
        client,
        group_id: str,
    ) -> dict:
        return await client._make_request("DELETE", f"delete_group/{group_id}")

    @staticmethod
    async def list_groups(
        client,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return await client._make_request("GET", "list_groups", params=params)

    @staticmethod
    async def add_user_to_group(
        client,
        user_id: str,
        group_id: str,
    ) -> dict:
        data = {
            "user_id": user_id,
            "group_id": group_id,
        }
        return await client._make_request(
            "POST", "add_user_to_group", json=data
        )

    @staticmethod
    async def remove_user_from_group(
        client,
        user_id: str,
        group_id: str,
    ) -> dict:
        data = {
            "user_id": user_id,
            "group_id": group_id,
        }
        return await client._make_request(
            "POST", "remove_user_from_group", json=data
        )

    @staticmethod
    async def get_users_in_group(
        client,
        group_id: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return await client._make_request(
            "GET", f"get_users_in_group/{group_id}", params=params
        )

    @staticmethod
    async def get_groups_for_user(
        client,
        user_id: str,
    ) -> dict:
        return await client._make_request(
            "GET", f"get_groups_for_user/{user_id}"
        )

    @staticmethod
    async def groups_overview(
        client,
        group_ids: Optional[list[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> dict:
        params = {}
        if group_ids:
            params["group_ids"] = group_ids
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        return await client._make_request(
            "GET", "groups_overview", params=params
        )

    @staticmethod
    async def get_documents_in_group(
        client,
        group_id: str,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        params = {}
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        return await client._make_request(
            "GET", f"group/{group_id}/documents", params=params
        )
