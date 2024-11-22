from typing import Optional
from uuid import UUID

from core.base.abstractions import DataLevel, KGRunType

from ..models import KGCreationSettings, KGRunType

from shared.api.models.kg.responses import (
    WrappedGraphResponse,
    WrappedGraphsResponse,
)

from shared.api.models import (
    WrappedBooleanResponse,
    WrappedGenericMessageResponse,
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
        Create a new knowledge graph.

        Args:
            name (str): Name of the graph
            description (Optional[str]): Description of the graph

        Returns:
            WrappedKGCreationResponse: Creation results
        """

        data = {"name": name}

        if description:
            data["description"] = description

        return await self.client._make_request(
            "POST",
            "graphs",
            data=data,
            version="v3",
        )

    async def retrieve(
        self,
        id: str | UUID,
    ) -> WrappedGraphResponse:
        """
        Retrieve a specific graph by ID.

        Args:
            id (str | UUID): ID of the graph to retrieve

        Returns:
            Information about the graph
        """

        return await self.client._make_request(
            "GET",
            f"graphs/{str(id)}",
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
            ids (Optional[list[str | UUID]]): List of graph IDs to filter by
            offset (Optional[int]): Pagination offset
            limit (Optional[int]): Maximum number of graphs to return

        Returns:
            dict: List of graphs
        """

        params = {"offset": offset, "limit": limit}

        if ids:
            params["ids"] = [str(id) for id in ids]

        return await self.client._make_request(
            "GET",
            "graphs",
            params=params,
            version="v3",
        )

    async def update(
        self,
        id: str | UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> WrappedGraphResponse:
        """
        Update an existing graph.

        Args:
            id (str | UUID): ID of the graph to update
            name (Optional[str]): New name for the graph
            description (Optional[str]): New description for the graph

        Returns:
            Information about the updated graph
        """

        data = {}

        if name:
            data["name"] = name
        if description:
            data["description"] = description

        return await self.client._make_request(
            "POST",
            f"graphs/{str(id)}",
            data=data,
            version="v3",
        )

    async def delete(
        self,
        id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Delete a graph.
        """

        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(id)}",
            version="v3",
        )

    async def tune_prompt(
        self,
        collection_id: str | UUID,
        prompt_name: str,
        documents_offset: Optional[int] = 0,
        documents_limit: Optional[int] = 100,
        chunks_offset: Optional[int] = 0,
        chunks_limit: Optional[int] = 100,
    ):  # -> WrappedKGTunePromptResponse:
        """
        Tune a graph-related prompt using collection data.

        Args:
            collection_id (Union[str, UUID]): Collection ID to tune prompt for
            prompt_name (str): Name of prompt to tune (graphrag_relationships_extraction_few_shot,
                             graphrag_entity_description, or graphrag_communities)
            documents_offset (int): Document pagination offset
            documents_limit (int): Maximum number of documents to use
            chunks_offset (int): Chunk pagination offset
            chunks_limit (int): Maximum number of chunks to use

        Returns:
            WrappedKGTunePromptResponse: Tuned prompt results
        """

        # TODO: Test this

        data = {
            "prompt_name": prompt_name,
            "documents_offset": documents_offset,
            "documents_limit": documents_limit,
            "chunks_offset": chunks_offset,
            "chunks_limit": chunks_limit,
        }

        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/tune-prompt",
            json=data,
            version="v3",
        )

    async def add_entity(
        self,
        id: str | UUID,
        entity_id: str | UUID,
    ) -> WrappedGenericMessageResponse:
        """
        Add an entity to a graph.

        Args:
            id (str | UUID): ID of the graph to add the entity to
            entity_id (str | UUID): ID of the entity to add to the graph

        Returns:
            A message indicating the result of the operation
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
            id (str | UUID): ID of the graph to remove the entity from
            entity_id (str | UUID): ID of the entity to remove from the graph

        Returns:
            Whether the entity was removed successfully
        """

        return await self.client._make_request(
            "DELETE",
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
            id (str | UUID): ID of the graph to add the relationship to
            relationship_id (str | UUID): ID of the relationship to add to the graph

        Returns:
            A message indicating the result of the operation
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
            id (str | UUID): ID of the graph to remove the relationship from
            relationship_id (str | UUID): ID of the relationship to remove from the graph

        Returns:
            Whether the relationship was removed successfully
        """

        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(id)}/relationships/{str(relationship_id)}",
            version="v3",
        )

    async def add_document(
        self,
        id: str | UUID,
        document_id: str | UUID,
    ) -> WrappedGenericMessageResponse:
        """
        Add all entities and relationships of a document to a graph.

        Args:
            id (str | UUID): ID of the graph to add the document to
            document_id (str | UUID): ID of the document to add to the graph

        Returns:
            A message indicating the result of the operation
        """

        return await self.client._make_request(
            "POST",
            f"graphs/{str(id)}/documents/{str(document_id)}",
            version="v3",
        )

    async def remove_document(
        self,
        id: str | UUID,
        document_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove all entities and relationships of a document from a graph.

        Args:
            id (str | UUID): ID of the graph to remove the document from
            document_id (str | UUID): ID of the document to remove from the graph

        Returns:
            Whether the document was removed successfully
        """

        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(id)}/documents/{str(document_id)}",
            version="v3",
        )

    async def add_collection(
        self,
        id: str | UUID,
        collection_id: str | UUID,
    ) -> WrappedGenericMessageResponse:
        """
        Add all entities and relationships of a collection to a graph.

        Args:
            id (str | UUID): ID of the graph to add the collection to
            collection_id (str | UUID): ID of the collection to add to the graph

        Returns:
            A message indicating the result of the operation
        """

        return await self.client._make_request(
            "POST",
            f"graphs/{str(id)}/collections/{str(collection_id)}",
            version="v3",
        )

    async def remove_collection(
        self,
        id: str | UUID,
        collection_id: str | UUID,
    ) -> WrappedBooleanResponse:
        """
        Remove all entities and relationships of a collection from a graph.
        """

        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(id)}/collections/{str(collection_id)}",
            version="v3",
        )
