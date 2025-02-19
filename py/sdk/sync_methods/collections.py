from typing import Any, Optional
from uuid import UUID

from shared.api.models import (
    WrappedBooleanResponse,
    WrappedCollectionResponse,
    WrappedCollectionsResponse,
    WrappedDocumentsResponse,
    WrappedGenericMessageResponse,
    WrappedUsersResponse,
)


class CollectionsSDK:
    def __init__(self, client):
        self.client = client

    def create(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> WrappedCollectionResponse:
        """Create a new collection.

        Args:
            name (str): Name of the collection
            description (Optional[str]): Description of the collection

        Returns:
            WrappedCollectionResponse
        """
        data: dict[str, Any] = {"name": name, "description": description}
        response_dict = self.client._make_request(
            "POST",
            "collections",
            json=data,
            version="v3",
        )

        return WrappedCollectionResponse(**response_dict)

    def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedCollectionsResponse:
        """List collections with pagination and filtering options.

        Args:
            ids (Optional[list[str | UUID]]): Filter collections by ids
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedCollectionsResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = ids

        response_dict = self.client._make_request(
            "GET", "collections", params=params, version="v3"
        )

        return WrappedCollectionsResponse(**response_dict)

    def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedCollectionResponse:
        """Get detailed information about a specific collection.

        Args:
            id (str | UUID): Collection ID to retrieve

        Returns:
            WrappedCollectionResponse
        """
        response_dict = self.client._make_request(
            "GET", f"collections/{str(id)}", version="v3"
        )

        return WrappedCollectionResponse(**response_dict)

    def update(
        self,
        id: str | UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        generate_description: Optional[bool] = False,
    ) -> WrappedCollectionResponse:
        """Update collection information.

        Args:
            id (str | UUID): Collection ID to update
            name (Optional[str]): Optional new name for the collection
            description (Optional[str]): Optional new description for the collection
            generate_description (Optional[bool]): Whether to generate a new synthetic description for the collection.

        Returns:
            WrappedCollectionResponse
        """
        data: dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description
        if generate_description:
            data["generate_description"] = str(generate_description)

        response_dict = self.client._make_request(
            "POST",
            f"collections/{str(id)}",
            json=data,
            version="v3",
        )

        return WrappedCollectionResponse(**response_dict)

    def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Delete a collection.

        Args:
            id (str | UUID): Collection ID to delete

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE", f"collections/{str(id)}", version="v3"
        )

        return WrappedBooleanResponse(**response_dict)

    def list_documents(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedDocumentsResponse:
        """List all documents in a collection.

        Args:
            id (str | UUID): Collection ID
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedDocumentsResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }

        response_dict = self.client._make_request(
            "GET",
            f"collections/{str(id)}/documents",
            params=params,
            version="v3",
        )

        return WrappedDocumentsResponse(**response_dict)

    def add_document(
        self,
        id: str | UUID,
        document_id: str | UUID,
    ) -> WrappedGenericMessageResponse:
        """Add a document to a collection.

        Args:
            id (str | UUID): Collection ID
            document_id (str | UUID): Document ID to add

        Returns:
            WrappedGenericMessageResponse
        """
        response_dict = self.client._make_request(
            "POST",
            f"collections/{str(id)}/documents/{str(document_id)}",
            version="v3",
        )

        return WrappedGenericMessageResponse(**response_dict)

    def remove_document(
        self,
        id: str | UUID,
        document_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Remove a document from a collection.

        Args:
            id (str | UUID): Collection ID
            document_id (str | UUID): Document ID to remove

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE",
            f"collections/{str(id)}/documents/{str(document_id)}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def list_users(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedUsersResponse:
        """List all users in a collection.

        Args:
            id (str, UUID): Collection ID
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedUsersResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }

        response_dict = self.client._make_request(
            "GET", f"collections/{str(id)}/users", params=params, version="v3"
        )

        return WrappedUsersResponse(**response_dict)

    def add_user(
        self,
        id: str | UUID,
        user_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Add a user to a collection.

        Args:
            id (str | UUID): Collection ID
            user_id (str | UUID): User ID to add

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "POST", f"collections/{str(id)}/users/{str(user_id)}", version="v3"
        )

        return WrappedBooleanResponse(**response_dict)

    def remove_user(
        self,
        id: str | UUID,
        user_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Remove a user from a collection.

        Args:
            id (str | UUID): Collection ID
            user_id (str | UUID): User ID to remove

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE",
            f"collections/{str(id)}/users/{str(user_id)}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def extract(
        self,
        id: str | UUID,
        settings: Optional[dict] = None,
        run_with_orchestration: Optional[bool] = True,
    ) -> WrappedGenericMessageResponse:
        """Extract entities and relationships from documents in a collection.

        Args:
            id (str | UUID): Collection ID to extract from
            settings (Optional[dict]): Settings for the entities and relationships extraction process
            run_with_orchestration (Optional[bool]): Whether to run the extraction process with orchestration.
                Defaults to True

        Returns:
            WrappedGenericMessageResponse
        """
        params = {"run_with_orchestration": run_with_orchestration}

        data: dict[str, Any] = {}
        if settings is not None:
            data["settings"] = settings

        response_dict = self.client._make_request(
            "POST",
            f"collections/{str(id)}/extract",
            params=params,
            json=data or None,
            version="v3",
        )

        return WrappedGenericMessageResponse(**response_dict)

    def retrieve_by_name(
        self, name: str, owner_id: Optional[str] = None
    ) -> WrappedCollectionResponse:
        """Retrieve a collection by its name.

        For non-superusers, the backend will use the authenticated user's ID.
        For superusers, the caller must supply an owner_id to restrict the search.

        Args:
            name (str): The name of the collection to retrieve.
            owner_id (Optional[str]): The owner ID to restrict the search. Required for superusers.

        Returns:
            WrappedCollectionResponse
        """
        query_params: dict[str, Any] = {}
        if owner_id is not None:
            query_params["owner_id"] = owner_id

        response_dict = self.client._make_request(
            "GET",
            f"collections/name/{name}",
            params=query_params,
            version="v3",
        )
        return WrappedCollectionResponse(**response_dict)
