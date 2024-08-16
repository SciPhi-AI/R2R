import uuid
from typing import Optional

from r2r.base import VectorDBFilterValue


class ManagementMethods:
    @staticmethod
    async def server_stats(client) -> dict:
        return await client._make_request("GET", "server_stats")

    @staticmethod
    async def update_prompt(
        client,
        name: str,
        template: Optional[str] = None,
        input_types: Optional[dict[str, str]] = {},
    ) -> dict:
        data = {
            "name": name,
            "template": template,
            "input_types": input_types,
        }
        return await client._make_request("POST", "update_prompt", json=data)

    @staticmethod
    async def logs(
        client,
        run_type_filter: Optional[str] = None,
        max_runs: int = 100,
    ) -> dict:
        params = {
            "run_type_filter": run_type_filter,
            "max_runs": max_runs,
        }
        return await client._make_request("GET", "logs", params=params)

    @staticmethod
    async def app_settings(client) -> dict:
        return await client._make_request("GET", "app_settings")

    @staticmethod
    async def score_completion(
        client,
        message_id: uuid.UUID,
        score: float = 0.0,
    ) -> dict:
        data = {
            "message_id": str(message_id),
            "score": score,
        }
        return await client._make_request(
            "POST", "score_completion", json=data
        )

    @staticmethod
    async def users_overview(
        client,
        user_ids: Optional[list[uuid.UUID]] = None,
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
        filters: dict[str, VectorDBFilterValue],
    ) -> dict:
        return await client._make_request(
            "DELETE", "delete", json={"filters": filters}
        )

    @staticmethod
    async def documents_overview(
        client,
        user_ids: Optional[list[uuid.UUID]] = None,
        group_ids: Optional[list[uuid.UUID]] = None,
        document_ids: Optional[list[uuid.UUID]] = None,
    ) -> dict:
        params = {
            "user_ids": [str(uid) for uid in user_ids] if user_ids else None,
            "group_ids": (
                [str(gid) for gid in group_ids] if group_ids else None
            ),
            "document_ids": (
                [str(did) for did in document_ids] if document_ids else None
            ),
        }
        return await client._make_request(
            "GET", "documents_overview", params=params
        )

    @staticmethod
    async def document_chunks(
        client,
        document_id: uuid.UUID,
    ) -> dict:
        return await client._make_request(
            "GET", f"document_chunks/{document_id}"
        )

    @staticmethod
    async def inspect_knowledge_graph(
        client,
        limit: int = 10000,
    ) -> str:
        params = {"limit": limit}
        return await client._make_request(
            "GET", "inspect_knowledge_graph", params=params
        )

    @staticmethod
    async def assign_document_to_group(
        client,
        document_id: str,
        group_id: uuid.UUID,
    ) -> dict:
        data = {
            "document_id": document_id,
            "group_id": str(group_id),
        }
        return await client._make_request(
            "POST", "assign_document_to_group", json=data
        )

    @staticmethod
    async def remove_document_from_group(
        client,
        document_id: str,
        group_id: uuid.UUID,
    ) -> dict:
        data = {
            "document_id": document_id,
            "group_id": str(group_id),
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
        description: str = "",
    ) -> dict:
        data = {
            "name": name,
            "description": description,
        }
        return await client._make_request("POST", "create_group", json=data)

    @staticmethod
    async def get_group(
        client,
        group_id: uuid.UUID,
    ) -> dict:
        return await client._make_request("GET", f"get_group/{group_id}")

    @staticmethod
    async def update_group(
        client,
        group_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        data = {
            "group_id": str(group_id),
            "name": name,
            "description": description,
        }
        return await client._make_request("PUT", "update_group", json=data)

    @staticmethod
    async def delete_group(
        client,
        group_id: uuid.UUID,
    ) -> dict:
        return await client._make_request("DELETE", f"delete_group/{group_id}")

    @staticmethod
    async def list_groups(
        client,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        params = {
            "offset": offset,
            "limit": limit,
        }
        return await client._make_request("GET", "list_groups", params=params)

    @staticmethod
    async def add_user_to_group(
        client,
        user_id: uuid.UUID,
        group_id: uuid.UUID,
    ) -> dict:
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
        user_id: uuid.UUID,
        group_id: uuid.UUID,
    ) -> dict:
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
        group_id: uuid.UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        params = {
            "offset": offset,
            "limit": limit,
        }
        return await client._make_request(
            "GET", f"get_users_in_group/{group_id}", params=params
        )

    @staticmethod
    async def get_groups_for_user(
        client,
        user_id: uuid.UUID,
    ) -> dict:
        return await client._make_request(
            "GET", f"get_groups_for_user/{user_id}"
        )

    @staticmethod
    async def groups_overview(
        client,
        group_ids: Optional[list[uuid.UUID]] = None,
    ) -> dict:
        params = {
            "group_ids": [str(gid) for gid in group_ids] if group_ids else None
        }
        return await client._make_request(
            "GET", "groups_overview", params=params
        )

    @staticmethod
    async def get_documents_in_group(
        client,
        group_id: uuid.UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        params = {
            "offset": offset,
            "limit": limit,
        }
        return await client._make_request(
            "GET", f"group/{group_id}/documents", params=params
        )
