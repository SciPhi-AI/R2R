from typing import Optional
from uuid import UUID

from shared.api.models.base import (
    WrappedBooleanResponse,
    WrappedGenericMessageResponse,
)

from shared.api.models.kg.responses import (
    WrappedGraphResponse,
    WrappedGraphsResponse,
    WrappedEntitiesResponse,
    WrappedEntityResponse,
    WrappedRelationshipResponse,
    WrappedRelationshipsResponse,
    # WrappedCommunitiesResponse,
    # WrappedCommunityResponse,
)


class GraphsSDK:
    """
    SDK for interacting with knowledge graphs in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> WrappedGraphResponse:
        """
        Create a new graph.

        Args:
            name (str): Name of the graph
            description (Optional[str]): Description of the graph

        Returns:
            dict: Created graph information
        """
        data = {"name": name, "description": description}
        return await self.client._make_request(
            "POST",
            "graphs",
            json=data,
            version="v3",
        )

    async def list(
        self,
        ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedGraphsResponse:
        """
        List graphs with pagination and filtering options.

        Args:
            ids (Optional[list[str | UUID]]): Filter graphs by ids
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of graphs and pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if ids:
            params["ids"] = ids

        return await self.client._make_request(
            "GET", "graphs", params=params, version="v3"
        )

    async def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedGraphResponse:
        """
        Get detailed information about a specific graph.

        Args:
            id (str | UUID): Graph ID to retrieve

        Returns:
            dict: Detailed graph information
        """
        return await self.client._make_request(
            "GET", f"graphs/{str(id)}", version="v3"
        )

    async def update(
        self,
        id: str | UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> WrappedGraphResponse:
        """
        Update graph information.

        Args:
            id (str | UUID): Graph ID to update
            name (Optional[str]): Optional new name for the graph
            description (Optional[str]): Optional new description for the graph

        Returns:
            dict: Updated graph information
        """
        data = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        return await self.client._make_request(
            "POST",
            f"graphs/{str(id)}",
            json=data,
            version="v3",
        )

    async def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Delete a graph.

        Args:
            id (str | UUID): Graph ID to delete

        Returns:
            bool: True if deletion was successful
        """
        result = await self.client._make_request(
            "DELETE", f"graphs/{str(id)}", version="v3"
        )
        return result.get("results", True)

    async def add_entity(
        self,
        id: str | UUID,
        entity_id: str | UUID,
    ) -> WrappedGenericMessageResponse:
        """
        Add an entity to a graph.

        Args:
            id (str | UUID): Graph ID to add entity to
            entity_id (str | UUID): Entity ID to add to the graph

        Returns:
            dict: Success message
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(id)}/entities/{str(entity_id)}",
            version="v3",
        )

    async def remove_entity(
        self,
        id: str | UUID,
        entity_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove an entity from a graph.

        Args:
            id (str | UUID): Graph ID to remove entity from
            entity_id (str | UUID): Entity ID to remove from the graph

        Returns:
            dict: Success message
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(id)}/entities/{str(entity_id)}",
            version="v3",
        )

    async def list_entities(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedEntitiesResponse:
        """
        List entities in a graph.

        Args:
            id (str | UUID): Graph ID to list entities from
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of entities and pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }

        return await self.client._make_request(
            "GET",
            f"graphs/{str(id)}/entities",
            params=params,
            version="v3",
        )

    async def get_entity(
        self,
        id: str | UUID,
        entity_id: str | UUID,
    ) -> WrappedEntityResponse:
        """
        Get entity information in a graph.

        Args:
            id (str | UUID): Graph ID to get entity from
            entity_id (str | UUID): Entity ID to get from the graph

        Returns:
            dict: Entity information
        """
        return await self.client._make_request(
            "GET",
            f"graphs/{str(id)}/entities/{str(entity_id)}",
            version="v3",
        )

    async def add_relationship(
        self,
        id: str | UUID,
        relationship_id: str | UUID,
    ) -> WrappedGenericMessageResponse:
        """
        Add a relationship to a graph.

        Args:
            id (str | UUID): Graph ID to add relationship to
            relationship_id (str | UUID): Relationship ID to add to the graph

        Returns:
            dict: Success message
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(id)}/relationships/{str(relationship_id)}",
            version="v3",
        )

    async def remove_relationship(
        self,
        id: str | UUID,
        relationship_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove a relationship from a graph.

        Args:
            id (str | UUID): Graph ID to remove relationship from
            relationship_id (str | UUID): Relationship ID to remove from the graph

        Returns:
            dict: Success message
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(id)}/relationships/{str(relationship_id)}",
            version="v3",
        )

    async def list_relationships(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedRelationshipsResponse:
        """
        List relationships in a graph.

        Args:
            id (str | UUID): Graph ID to list relationships from
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of relationships and pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }

        return await self.client._make_request(
            "GET",
            f"graphs/{str(id)}/relationships",
            params=params,
            version="v3",
        )

    async def get_relationship(
        self,
        id: str | UUID,
        relationship_id: str | UUID,
    ) -> WrappedRelationshipResponse:
        """
        Get relationship information in a graph.

        Args:
            id (str | UUID): Graph ID to get relationship from
            relationship_id (str | UUID): Relationship ID to get from the graph

        Returns:
            dict: Relationship information
        """
        return await self.client._make_request(
            "GET",
            f"graphs/{str(id)}/relationships/{str(relationship_id)}",
            version="v3",
        )

    async def add_community(
        self,
        id: str | UUID,
        community_id: str | UUID,
    ) -> WrappedGenericMessageResponse:
        """
        Add a community to a graph.

        Args:
            id (str | UUID): Graph ID to add community to
            community_id (str | UUID): Community ID to add to the graph

        Returns:
            dict: Success message
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(id)}/communities/{str(community_id)}",
            version="v3",
        )

    async def remove_community(
        self,
        id: str | UUID,
        community_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove a community from a graph.

        Args:
            id (str | UUID): Graph ID to remove community from
            community_id (str | UUID): Community ID to remove from the graph

        Returns:
            dict: Success message
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(id)}/communities/{str(community_id)}",
            version="v3",
        )

    async def list_communities(
        self,
        id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ):  # -> WrappedCommunitiesResponse
        """
        List communities in a graph.

        Args:
            id (str | UUID): Graph ID to list communities from
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            dict: List of communities and pagination information
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }

        return await self.client._make_request(
            "GET",
            f"graphs/{str(id)}/communities",
            params=params,
            version="v3",
        )

    async def get_community(
        self,
        id: str | UUID,
        community_id: str | UUID,
    ):  # -> WrappedCommunityResponse
        """
        Get community information in a graph.

        Args:
            id (str | UUID): Graph ID to get community from
            community_id (str | UUID): Community ID to get from the graph

        Returns:
            dict: Community information
        """
        return await self.client._make_request(
            "GET",
            f"graphs/{str(id)}/communities/{str(community_id)}",
            version="v3",
        )
