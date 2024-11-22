import json
from io import BytesIO
from typing import Optional
from uuid import UUID

from shared.api.models.base import WrappedBooleanResponse
from shared.api.models.management.responses import (
    WrappedChunksResponse,
    WrappedCollectionsResponse,
    WrappedDocumentResponse,
    WrappedDocumentsResponse,
)
from shared.api.models.kg.responses import (
    WrappedEntityResponse,
    WrappedEntitiesResponse,
)


class EntitiesSDK:
    """
    SDK for interacting with entities in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        name: str,
        description: Optional[str] = None,
        category: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> WrappedEntityResponse:
        """
        Create a new entity in the graph.

        Args:
            name (str): The name of the entity.
            description (Optional[str]): The description of the entity.
            category (Optional[str]): The category of the entity.
            attributes (Optional[dict]): The attributes of the entity.
        """

        data = {}
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if category:
            data["category"] = category
        if attributes:
            data["attributes"] = attributes

        return await self.client._make_request(
            "POST",
            "entities",
            data=data,
            version="v3",
        )

    async def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedEntityResponse:
        """
        Retrieve a specific entity by ID.

        Args:
            id (str | UUID): The ID of the entity to retrieve.

        Returns:
            dict: Entity information.
        """

        return await self.client._make_request(
            "GET",
            f"entities/{str(id)}",
            version="v3",
        )

    async def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedEntitiesResponse:
        """
        List entities with pagination.

        Args:
            ids (Optional[list[str | UUID]]): Optional list of entity IDs to filter by.
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of entities and pagination information.
        """

        params = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = [str(entity_id) for entity_id in ids]  # type: ignore

        return await self.client._make_request(
            "GET",
            "entities",
            params=params,
            version="v3",
        )

    async def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Delete a specific entity by ID.

        Args:
            id (str | UUID): The ID of the entity to delete.
        """

        return await self.client._make_request(
            "DELETE",
            f"entities/{str(id)}",
            version="v3",
        )

    async def update(
        self,
        id: str | UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        attributes: Optional[dict] = None,
        category: Optional[str] = None,
    ) -> WrappedEntityResponse:
        """
        Update a specific entity by ID.

        Args:
            id (str | UUID): The ID of the entity to update.
            name (Optional[str]): The name of the entity.
            description (Optional[str]): The description of the entity.
            attributes (Optional[dict]): The attributes of the entity.
            category (Optional[str]): The category of the entity.

        Returns:
            dict: Updated results containing entity information.
        """

        data = {}
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if attributes:
            data["attributes"] = attributes
        if category:
            data["category"] = category

        return await self.client._make_request(
            "POST",
            f"entities/{str(id)}",
            data=data,
            version="v3",
        )
