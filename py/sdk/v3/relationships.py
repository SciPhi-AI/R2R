import json
from io import BytesIO
from typing import Optional
from uuid import UUID

from shared.api.models.base import WrappedBooleanResponse

from shared.api.models.kg.responses import (
    WrappedRelationshipResponse,
    WrappedRelationshipsResponse,
)


class RelationshipsSDK:
    """
    SDK for interacting with relationships in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        subject: str,
        predicate: str,
        object: str,
        description: str,
        weight: Optional[float] = 1.0,
        attributes: Optional[dict] = None,
    ) -> WrappedRelationshipResponse:
        """
        Create a new entity in the graph.

        Args:
            subject (str): The subject of the relationship.
            predicate (str): The predicate of the relationship.
            object (str): The object of the relationship.
            description (str): The description of the relationship.
            weight (Optional[float]): The weight of the relationship.
            attributes (Optional[dict]): The attributes of the relationship.
        """

        data = {}
        if subject:
            data["subject"] = subject
        if predicate:
            data["predicate"] = predicate
        if object:
            data["description"] = description
        if description:
            data["description"] = description
        if weight:
            data["weight"] = weight
        if attributes:
            data["attributes"] = attributes

        return await self.client._make_request(
            "POST",
            "relationships",
            data=data,
            version="v3",
        )

    async def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedRelationshipResponse:
        """
        Retrieve a specific relationship by ID.

        Args:
            id (str | UUID): The ID of the relationship to retrieve.

        Returns:
            dict: Relationship information.
        """

        return await self.client._make_request(
            "GET",
            f"relationships/{str(id)}",
            version="v3",
        )

    async def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedRelationshipsResponse:
        """
        List relationships with pagination.

        Args:
            ids (Optional[list[str | UUID]]): Optional list of relationship IDs to filter by.
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of relationships and pagination information.
        """

        params = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = [str(entity_id) for entity_id in ids]  # type: ignore

        return await self.client._make_request(
            "GET",
            "relationships",
            params=params,
            version="v3",
        )

    async def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Delete a specific relationship by ID.

        Args:
            id (str | UUID): The ID of the relationship to delete.
        """

        return await self.client._make_request(
            "DELETE",
            f"relationships/{str(id)}",
            version="v3",
        )

    async def update(
        self,
        id: str | UUID,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        description: Optional[str] = None,
        weight: Optional[float] = None,
        attributes: Optional[dict] = None,
    ) -> WrappedRelationshipResponse:
        """
        Update a specific relationship by ID.

        Args:
            id (str | UUID): The ID of the relationship to update.
            subject (Optional[str]): The subject of the relationship.
            predicate (Optional[str]): The predicate of the relationship.
            object (Optional[str]): The object of the relationship.
            description (Optional[str]): The description of the relationship.
            weight (Optional[float]): The weight of the relationship.
            attributes (Optional[dict]): The attributes of the relationship.

        Returns:
            dict: Updated results containing relationship information.
        """

        data = {}
        if subject:
            data["subject"] = subject
        if predicate:
            data["predicate"] = predicate
        if object:
            data["object"] = object
        if description:
            data["description"] = description
        if attributes:
            data["attributes"] = attributes
        if weight:
            data["weight"] = weight

        return await self.client._make_request(
            "POST",
            f"relationships/{str(id)}",
            data=data,
            version="v3",
        )
