from builtins import list as _list
from typing import Any, Optional
from uuid import UUID

from shared.api.models import (
    WrappedBooleanResponse,
    WrappedCommunitiesResponse,
    WrappedCommunityResponse,
    WrappedEntitiesResponse,
    WrappedEntityResponse,
    WrappedGenericMessageResponse,
    WrappedGraphResponse,
    WrappedGraphsResponse,
    WrappedRelationshipResponse,
    WrappedRelationshipsResponse,
)


class GraphsSDK:
    """SDK for interacting with knowledge graphs in the v3 API."""

    def __init__(self, client):
        self.client = client

    def list(
        self,
        collection_ids: Optional[list[str | UUID]] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedGraphsResponse:
        """List graphs with pagination and filtering options.

        Args:
            ids (Optional[list[str | UUID]]): Filter graphs by ids
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedGraphsResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }
        if collection_ids:
            params["collection_ids"] = collection_ids

        response_dict = self.client._make_request(
            "GET", "graphs", params=params, version="v3"
        )

        return WrappedGraphsResponse(**response_dict)

    def retrieve(
        self,
        collection_id: str | UUID,
    ) -> WrappedGraphResponse:
        """Get detailed information about a specific graph.

        Args:
            collection_id (str | UUID): Graph ID to retrieve

        Returns:
            WrappedGraphResponse
        """
        response_dict = self.client._make_request(
            "GET", f"graphs/{str(collection_id)}", version="v3"
        )

        return WrappedGraphResponse(**response_dict)

    def reset(
        self,
        collection_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Deletes a graph and all its associated data.

        This endpoint permanently removes the specified graph along with all
        entities and relationships that belong to only this graph.

        Entities and relationships extracted from documents are not deleted.

        Args:
            collection_id (str | UUID): Graph ID to reset

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "POST", f"graphs/{str(collection_id)}/reset", version="v3"
        )

        return WrappedBooleanResponse(**response_dict)

    def update(
        self,
        collection_id: str | UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> WrappedGraphResponse:
        """Update graph information.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            name (Optional[str]): Optional new name for the graph
            description (Optional[str]): Optional new description for the graph

        Returns:
            WrappedGraphResponse
        """
        data: dict[str, Any] = {}
        if name is not None:
            data["name"] = name
        if description is not None:
            data["description"] = description

        response_dict = self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}",
            json=data,
            version="v3",
        )

        return WrappedGraphResponse(**response_dict)

    def list_entities(
        self,
        collection_id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedEntitiesResponse:
        """List entities in a graph.

        Args:
            collection_id (str | UUID): Graph ID to list entities from
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedEntitiesResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }

        response_dict = self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/entities",
            params=params,
            version="v3",
        )

        return WrappedEntitiesResponse(**response_dict)

    def get_entity(
        self,
        collection_id: str | UUID,
        entity_id: str | UUID,
    ) -> WrappedEntityResponse:
        """Get entity information in a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            entity_id (str | UUID): Entity ID to get from the graph

        Returns:
            WrappedEntityResponse
        """
        response_dict = self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/entities/{str(entity_id)}",
            version="v3",
        )

        return WrappedEntityResponse(**response_dict)

    def remove_entity(
        self,
        collection_id: str | UUID,
        entity_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Remove an entity from a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            entity_id (str | UUID): Entity ID to remove from the graph

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/entities/{str(entity_id)}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def list_relationships(
        self,
        collection_id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedRelationshipsResponse:
        """List relationships in a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedRelationshipsResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }

        response_dict = self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/relationships",
            params=params,
            version="v3",
        )

        return WrappedRelationshipsResponse(**response_dict)

    def get_relationship(
        self,
        collection_id: str | UUID,
        relationship_id: str | UUID,
    ) -> WrappedRelationshipResponse:
        """Get relationship information in a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            relationship_id (str | UUID): Relationship ID to get from the graph

        Returns:
            WrappedRelationshipResponse
        """
        response_dict = self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/relationships/{str(relationship_id)}",
            version="v3",
        )

        return WrappedRelationshipResponse(**response_dict)

    def remove_relationship(
        self,
        collection_id: str | UUID,
        relationship_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Remove a relationship from a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            relationship_id (str | UUID): Relationship ID to remove from the graph

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/relationships/{str(relationship_id)}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def build(
        self,
        collection_id: str | UUID,
        settings: Optional[dict] = None,
        run_with_orchestration: bool = True,
    ) -> WrappedGenericMessageResponse:
        """Build a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            settings (dict): Settings for the build
            run_with_orchestration (bool, optional): Whether to run with orchestration. Defaults to True.

        Returns:
            WrappedGenericMessageResponse
        """
        data: dict[str, Any] = {
            "run_with_orchestration": run_with_orchestration,
        }
        if settings:
            data["settings"] = settings
        response_dict = self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/communities/build",
            json=data,
            version="v3",
        )

        return WrappedGenericMessageResponse(**response_dict)

    def list_communities(
        self,
        collection_id: str | UUID,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> WrappedCommunitiesResponse:
        """List communities in a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

        Returns:
            WrappedCommunitiesResponse
        """
        params: dict = {
            "offset": offset,
            "limit": limit,
        }

        response_dict = self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/communities",
            params=params,
            version="v3",
        )

        return WrappedCommunitiesResponse(**response_dict)

    def get_community(
        self,
        collection_id: str | UUID,
        community_id: str | UUID,
    ) -> WrappedCommunityResponse:
        """Get community information in a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            community_id (str | UUID): Community ID to get from the graph

        Returns:
            WrappedCommunityResponse
        """
        response_dict = self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
            version="v3",
        )

        return WrappedCommunityResponse(**response_dict)

    def update_community(
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
        """Update community information.

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
            WrappedCommunityResponse
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

        response_dict = self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
            json=data,
            version="v3",
        )

        return WrappedCommunityResponse(**response_dict)

    def delete_community(
        self,
        collection_id: str | UUID,
        community_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Remove a community from a graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            community_id (str | UUID): Community ID to remove from the graph

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def pull(
        self,
        collection_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Adds documents to a graph by copying their entities and
        relationships.

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

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/pull",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def remove_document(
        self,
        collection_id: str | UUID,
        document_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """Removes a document from a graph and removes any associated entities.

        This endpoint:
            1. Removes the document ID from the graph's document_ids array
            2. Optionally deletes the document's copied entities and relationships

        The user must have access to both the graph and the document being removed.

        Returns:
            WrappedBooleanResponse
        """
        response_dict = self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/documents/{str(document_id)}",
            version="v3",
        )

        return WrappedBooleanResponse(**response_dict)

    def create_entity(
        self,
        collection_id: str | UUID,
        name: str,
        description: str,
        category: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> WrappedEntityResponse:
        """Creates a new entity in the graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            name (str): The name of the entity to create
            description (Optional[str]): The description of the entity
            category (Optional[str]): The category of the entity
            metadata (Optional[dict]): Additional metadata for the entity

        Returns:
            WrappedEntityResponse
        """
        data: dict[str, Any] = {
            "name": name,
            "description": description,
        }
        if category is not None:
            data["category"] = category
        if metadata is not None:
            data["metadata"] = metadata

        response_dict = self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/entities",
            json=data,
            version="v3",
        )

        return WrappedEntityResponse(**response_dict)

    def create_relationship(
        self,
        collection_id: str | UUID,
        subject: str,
        subject_id: str | UUID,
        predicate: str,
        object: str,
        object_id: str | UUID,
        description: str,
        weight: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> WrappedRelationshipResponse:
        """Creates a new relationship in the graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            subject (str): The subject of the relationship
            subject_id (str | UUID): The ID of the subject entity
            predicate (str): The predicate/type of the relationship
            object (str): The object of the relationship
            object_id (str | UUID): The ID of the object entity
            description (Optional[str]): Description of the relationship
            weight (Optional[float]): Weight/strength of the relationship
            metadata (Optional[dict]): Additional metadata for the relationship

        Returns:
            WrappedRelationshipResponse
        """
        data: dict[str, Any] = {
            "subject": subject,
            "subject_id": str(subject_id),
            "predicate": predicate,
            "object": object,
            "object_id": str(object_id),
            "description": description,
        }
        if weight is not None:
            data["weight"] = weight
        if metadata is not None:
            data["metadata"] = metadata

        response_dict = self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/relationships",
            json=data,
            version="v3",
        )

        return WrappedRelationshipResponse(**response_dict)

    def create_community(
        self,
        collection_id: str | UUID,
        name: str,
        summary: str,
        findings: Optional[_list[str]] = None,
        rating: Optional[float] = None,
        rating_explanation: Optional[str] = None,
    ) -> WrappedCommunityResponse:
        """Creates a new community in the graph.

        Args:
            collection_id (str | UUID): The collection ID corresponding to the graph
            name (str): The name of the community
            summary (str): A summary description of the community
            findings (Optional[list[str]]): List of findings about the community
            rating (Optional[float]): Rating between 1 and 10
            rating_explanation (Optional[str]): Explanation for the rating

        Returns:
            WrappedCommunityResponse
        """
        data: dict[str, Any] = {
            "name": name,
            "summary": summary,
        }
        if findings is not None:
            data["findings"] = findings
        if rating is not None:
            data["rating"] = rating
        if rating_explanation is not None:
            data["rating_explanation"] = rating_explanation

        response_dict = self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/communities",
            json=data,
            version="v3",
        )

        return WrappedCommunityResponse(**response_dict)
