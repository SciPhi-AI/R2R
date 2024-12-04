from typing import Optional
from uuid import UUID

from shared.api.models.base import (
    WrappedBooleanResponse,
    WrappedGenericMessageResponse,
)
from shared.api.models.management.responses import (
    WrappedCollectionResponse,
    WrappedCollectionsResponse,
    WrappedDocumentResponse,
    WrappedUsersResponse,
)


class CollectionsSDK:
    def __init__(self, client):
        self.client = client

    async def create(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> WrappedCollectionResponse:
        """
        Create a new collection.

        Args:
            name (str): Name of the collection
            description (Optional[str]): Description of the collection

        Returns:
            dict: Created collection information
        """
        data = {"name": name, "description": description}
        return await self.client._make_request(
            "POST",
            "collections",
            json=data,
            version="v3",
        )

    async def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedCollectionsResponse:
        """
        List collections with pagination and filtering options.

        Args:
            ids (Optional[list[str | UUID]]): Filter collections by ids
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of collections and pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = ids

        return await self.client._make_request(
            "GET", "collections", params=params, version="v3"
        )

    async def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedCollectionResponse:
        """
        Get detailed information about a specific collection.

        Args:
            id (str | UUID): Collection ID to retrieve

        Returns:
            dict: Detailed collection information
        """
        return await self.client._make_request(
            "GET", f"collections/{str(id)}", version="v3"
        )

    async def update(
        self,
        id: str | UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> WrappedCollectionResponse:
        """
        Update collection information.

        Args:
            id (str | UUID): Collection ID to update
            name (Optional[str]): Optional new name for the collection
            description (Optional[str]): Optional new description for the collection

        Returns:
            dict: Updated collection information
        """
        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        return await self.client._make_request(
            "POST",
            f"collections/{str(id)}",
            json=data,
            version="v3",
        )

    async def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Delete a collection.

        Args:
            id (str | UUID): Collection ID to delete

        Returns:
            bool: True if deletion was successful
        """
        result = await self.client._make_request(
            "DELETE", f"collections/{str(id)}", version="v3"
        )
        return result.get("results", True)

    async def list_documents(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedDocumentResponse:
        """
        List all documents in a collection.

        Args:
            id (str | UUID): Collection ID
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of documents and pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }

        return await self.client._make_request(
            "GET",
            f"collections/{str(id)}/documents",
            params=params,
            version="v3",
        )

    async def add_document(
        self,
        id: str | UUID,
        document_id: str | UUID,
    ) -> WrappedGenericMessageResponse:
        """
        Add a document to a collection.

        Args:
            id (str | UUID): Collection ID
            document_id (str | UUID): Document ID to add

        Returns:
            dict: Result of the operation
        """
        return await self.client._make_request(
            "POST",
            f"collections/{str(id)}/documents/{str(document_id)}",
            version="v3",
        )

    async def remove_document(
        self,
        id: str | UUID,
        document_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove a document from a collection.

        Args:
            id (str | UUID): Collection ID
            document_id (str | UUID): Document ID to remove

        Returns:
            bool: True if removal was successful
        """
        result = await self.client._make_request(
            "DELETE",
            f"collections/{str(id)}/documents/{str(document_id)}",
            version="v3",
        )
        return result.get("results", True)

    async def list_users(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedUsersResponse:
        """
        List all users in a collection.

        Args:
            id (str, UUID): Collection ID
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of users and pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }

        return await self.client._make_request(
            "GET", f"collections/{str(id)}/users", params=params, version="v3"
        )

    async def add_user(
        self,
        id: str | UUID,
        user_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Add a user to a collection.

        Args:
            id (str | UUID): Collection ID
            user_id (str | UUID): User ID to add

        Returns:
            dict: Result of the operation
        """
        return await self.client._make_request(
            "POST", f"collections/{str(id)}/users/{str(user_id)}", version="v3"
        )

    async def remove_user(
        self,
        id: str | UUID,
        user_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove a user from a collection.

        Args:
            id (str | UUID): Collection ID
            user_id (str | UUID): User ID to remove

        Returns:
            bool: True if removal was successful
        """
        result = await self.client._make_request(
            "DELETE",
            f"collections/{str(id)}/users/{str(user_id)}",
            version="v3",
        )
        return result.get("results", True)

    async def extract(
        self,
        id: str | UUID,
        # run_type: Optional[str] = "RUN",
        settings: Optional[dict] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> dict:
        """
        Extract entities and relationships from documents in a collection.

        Args:
            id (str | UUID): Collection ID to extract from
            run_type (Optional[str]): Whether to return an estimate of the creation cost or to actually extract.
                Defaults to "RUN"
            settings (Optional[dict]): Settings for the entities and relationships extraction process
            run_with_orchestration (Optional[bool]): Whether to run the extraction process with orchestration.
                Defaults to True

        Returns:
            dict: Result of the extraction process, containing either:
                - For estimates: message, task_id, id, and estimate
                - For runs: message and task_id
        """
        params = {
            # "run_type": run_type,
            "run_with_orchestration": run_with_orchestration
        }

        data = {}
        if settings is not None:
            data["settings"] = settings

        return await self.client._make_request(
            "POST",
            f"collections/{str(id)}/extract",
            params=params,
            json=data if data else None,
            version="v3",
        )
