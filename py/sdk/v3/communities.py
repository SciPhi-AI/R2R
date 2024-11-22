import json
from io import BytesIO
from typing import Optional
from uuid import UUID

from shared.api.models.base import WrappedBooleanResponse
from shared.api.models.kg.responses import (
    WrappedCommunityResponse,
    WrappedCommunitiesResponse,
)


class CommunitiesSDK:
    """
    SDK for interacting with communities in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        graph_id: str | UUID,
        name: str,
        summary: str,
        findings: Optional[list[str]] = None,
        level: Optional[int] = None,
        rating: Optional[float] = None,
        rating_explanation: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> WrappedCommunityResponse:
        """
        Create a new community.

        Args:
            graph_id (str | UUID): The ID of the graph to create the community in.
            name (str): The name of the community.
            summary (str): The summary of the community.
            findings (Optional[list[str]]): The findings of the community.
            level (Optional[int]): The level of the community.
            rating (Optional[float]): The rating of the community.
            rating_explanation (Optional[str]): The rating explanation of the community.
            attributes (Optional[dict]): The attributes of the community.

        Returns:
            The created community.
        """

        data = {}
        if name:
            data["name"] = name
        if summary:
            data["summary"] = summary
        if findings:
            data["findings"] = findings
        if level:
            data["level"] = level
        if rating:
            data["rating"] = rating
        if rating_explanation:
            data["rating_explanation"] = rating_explanation
        if attributes:
            data["attributes"] = attributes

        return await self.client._make_request(
            "POST",
            f"graphs/{str(graph_id)}/communities",
            data=data,
            version="v3",
        )

    async def retrieve(
        self,
        id: str | UUID,
        community_id: str | UUID,
    ) -> WrappedCommunityResponse:
        """
        Retrieve a specific community by ID.

        Args:
            id (str | UUID): The ID of the graph to retrieve communities for.
            community_id (str | UUID): The ID of the community to retrieve.

        Returns:
            dict: Community information.
        """

        return await self.client._make_request(
            "GET",
            f"graphs/{str(id)}/communities/{str(community_id)}",
            version="v3",
        )

    async def update(
        self,
        id: str | UUID,
        community_id: str | UUID,
        name: Optional[str] = None,
        summary: Optional[str] = None,
        findings: Optional[list[str]] = None,
        level: Optional[int] = None,
        rating: Optional[float] = None,
        rating_explanation: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> WrappedCommunityResponse:
        """
        Update a specific community by ID.

        Args:
            id (str | UUID): The ID of the graph to update communities for.
            community_id (str | UUID): The ID of the community to update.
            name (Optional[str]): The name of the community.
            summary (Optional[str]): The summary of the community.
            findings (Optional[list[str]]): The findings of the community.
            level (Optional[int]): The level of the community.
            rating (Optional[float]): The rating of the community.
            rating_explanation (Optional[str]): The rating explanation of the community.
            attributes (Optional[dict]): The attributes of the community.

        Returns:
            dict: Updated results containing entity information.
        """

        data = {}
        if name:
            data["name"] = name
        if summary:
            data["summary"] = summary
        if findings:
            data["findings"] = findings
        if level:
            data["level"] = level
        if rating:
            data["rating"] = rating
        if rating_explanation:
            data["rating_explanation"] = rating_explanation
        if attributes:
            data["attributes"] = attributes

        return await self.client._make_request(
            "POST",
            f"graphs/{str(id)}/communities/{str(community_id)}",
            data=data,
            version="v3",
        )

    async def list(
        self,
        id: str | UUID,
        community_ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedCommunitiesResponse:
        """
        List communities with pagination.

        Args:
            id (str | UUID): The ID of the graph to list communities for.
            community_ids (Optional[list[str | UUID]]): Optional list of community IDs to filter by.
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of entities and pagination information.
        """

        params = {
            "offset": offset,
            "limit": limit,
        }
        if community_ids:
            params["ids"] = [str(community_id) for community_id in community_ids]  # type: ignore

        return await self.client._make_request(
            "GET",
            f"graphs/{str(id)}/communities",
            params=params,
            version="v3",
        )

    async def delete(
        self,
        id: str | UUID,
        community_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Delete a specific community by ID.

        Args:
            id (str | UUID): The ID of the graph to delete communities for.
            community_id (str | UUID): The ID of the community to delete.
        """

        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(id)}/communities/{str(community_id)}",
            version="v3",
        )
