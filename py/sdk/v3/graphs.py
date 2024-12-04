from typing import Any, Optional
from uuid import UUID

from shared.api.models.base import WrappedBooleanResponse
from shared.api.models.kg.responses import (
    WrappedCommunitiesResponse,
    WrappedCommunityResponse,
    WrappedEntitiesResponse,
    WrappedEntityResponse,
    WrappedGraphResponse,
    WrappedGraphsResponse,
    WrappedRelationshipResponse,
    WrappedRelationshipsResponse,
)

_list = list  # Required for type hinting since we have a list method


class GraphsSDK:
    """
    SDK for interacting with knowledge graphs in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def list(
        self,
        collection_ids: Optional[list[str | UUID]] = None,
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
        if collection_ids:
            params["collection_ids"] = collection_ids

        return await self.client._make_request(
            "GET", "graphs", params=params, version="v3"
        )

    async def retrieve(
        self,
        collection_id: str | UUID,
    ) -> WrappedGraphResponse:
        """
        Get detailed information about a specific graph.

        Args:
            collection_id (str | UUID): Graph ID to retrieve

        Returns:
            dict: Detailed graph information
        """
        return await self.client._make_request(
            "GET", f"graphs/{str(collection_id)}", version="v3"
        )

    async def reset(
        self,
        collection_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Deletes a graph and all its associated data.

        This endpoint permanently removes the specified graph along with all
        entities and relationships that belong to only this graph.

        Entities and relationships extracted from documents are not deleted.

        Args:
            collection_id (str | UUID): Graph ID to reset

        Returns:
            dict: Success message
        """
        return await self.client._make_request(
            "POST", f"graphs/{str(collection_id)}/reset", version="v3"
        )

    async def update(
        self,
        collection_id: str | UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> WrappedGraphResponse:
        """
        Update graph information.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
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
            f"graphs/{str(collection_id)}",
            json=data,
            version="v3",
        )

    # TODO: create entity

    async def list_entities(
        self,
        collection_id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedEntitiesResponse:
        """
        List entities in a graph.

        Args:
            collection_id (str | UUID): Graph ID to list entities from
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
            f"graphs/{str(collection_id)}/entities",
            params=params,
            version="v3",
        )

    async def get_entity(
        self,
        collection_id: str | UUID,
        entity_id: str | UUID,
    ) -> WrappedEntityResponse:
        """
        Get entity information in a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            entity_id (str | UUID): Entity ID to get from the graph

        Returns:
            dict: Entity information
        """
        return await self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/entities/{str(entity_id)}",
            version="v3",
        )

    # TODO: update entity

    async def remove_entity(
        self,
        collection_id: str | UUID,
        entity_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove an entity from a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            entity_id (str | UUID): Entity ID to remove from the graph

        Returns:
            dict: Success message
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/entities/{str(entity_id)}",
            version="v3",
        )

    # TODO: create relationship

    async def list_relationships(
        self,
        collection_id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedRelationshipsResponse:
        """
        List relationships in a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
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
            f"graphs/{str(collection_id)}/relationships",
            params=params,
            version="v3",
        )

    async def get_relationship(
        self,
        collection_id: str | UUID,
        relationship_id: str | UUID,
    ) -> WrappedRelationshipResponse:
        """
        Get relationship information in a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            relationship_id (str | UUID): Relationship ID to get from the graph

        Returns:
            dict: Relationship information
        """
        return await self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/relationships/{str(relationship_id)}",
            version="v3",
        )

    # TODO: update relationship

    async def remove_relationship(
        self,
        collection_id: str | UUID,
        relationship_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove a relationship from a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            relationship_id (str | UUID): Relationship ID to remove from the graph

        Returns:
            dict: Success message
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/relationships/{str(relationship_id)}",
            version="v3",
        )

    async def build(
        self,
        collection_id: str | UUID,
        settings: Optional[dict] = None,
        run_type: str = "estimate",
        run_with_orchestration: bool = True,
    ) -> WrappedBooleanResponse:
        """
        Build a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            settings (dict): Settings for the build
            run_type (str, optional): Type of build to run. Defaults to "estimate".
            run_with_orchestration (bool, optional): Whether to run with orchestration. Defaults to True.

        Returns:
            dict: Success message
        """
        data = {
            "run_type": run_type,
            "run_with_orchestration": run_with_orchestration,
        }
        if settings:
            data["settings"] = settings
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/communities/build",
            json=data,
            version="v3",
        )

    # TODO: create community

    async def list_communities(
        self,
        collection_id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedCommunitiesResponse:
        """
        List communities in a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
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
            f"graphs/{str(collection_id)}/communities",
            params=params,
            version="v3",
        )

    async def get_community(
        self,
        collection_id: str | UUID,
        community_id: str | UUID,
    ) -> WrappedCommunityResponse:
        """
        Get community information in a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            community_id (str | UUID): Community ID to get from the graph

        Returns:
            dict: Community information
        """
        return await self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
            version="v3",
        )

    async def update_community(
        self,
        collection_id: str | UUID,
        community_id: str | UUID,
        name: Optional[str] = None,
        summary: Optional[str] = None,
        findings: Optional[_list[str]] = None,
        rating: Optional[int] = None,
        rating_explanation: Optional[str] = None,
        level: Optional[int] = None,
        attributes: Optional[dict] = None,
    ) -> WrappedCommunityResponse:
        """
        Update community information.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            community_id (str | UUID): Community ID to update
            name (Optional[str]): Optional new name for the community
            summary (Optional[str]): Optional new summary for the community
            findings (Optional[list[str]]): Optional new findings for the community
            rating (Optional[int]): Optional new rating for the community
            rating_explanation (Optional[str]): Optional new rating explanation for the community
            level (Optional[int]): Optional new level for the community
            attributes (Optional[dict]): Optional new attributes for the community

        Returns:
            dict: Updated community information
        """
        data: dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if summary is not None:
            data["summary"] = summary
        if findings is not None:
            data["findings"] = findings
        if rating is not None:
            data["rating"] = str(rating)
        if rating_explanation is not None:
            data["rating_explanation"] = rating_explanation
        if level is not None:
            data["level"] = level
        if attributes is not None:
            data["attributes"] = attributes

        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
            json=data,
            version="v3",
        )

    async def delete_community(
        self,
        collection_id: str | UUID,
        community_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove a community from a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            community_id (str | UUID): Community ID to remove from the graph

        Returns:
            dict: Success message
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
            version="v3",
        )

    async def pull(
        self,
        collection_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Adds documents to a graph by copying their entities and relationships.

        This endpoint:
            1. Copies document entities to the graphs_entities table
            2. Copies document relationships to the graphs_relationships table
            3. Associates the documents with the graph

        When a document is added:
            - Its entities and relationships are copied to graph-specific tables
            - Existing entities/relationships are updated by merging their properties
            - The document ID is recorded in the graph's document_ids array

        Documents added to a graph will contribute their knowledge to:
            - Graph analysis and querying
            - Community detection
            - Knowledge graph enrichment
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/pull",
            version="v3",
        )

    async def remove_document(
        self,
        collection_id: str | UUID,
        document_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Removes a document from a graph and removes any associated entities

        This endpoint:
            1. Removes the document ID from the graph's document_ids array
            2. Optionally deletes the document's copied entities and relationships

        The user must have access to both the graph and the document being removed.
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/documents/{str(document_id)}",
            version="v3",
        )
