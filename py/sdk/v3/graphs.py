import json
from inspect import getmembers, isasyncgenfunction, iscoroutinefunction
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from ..base.base_client import sync_generator_wrapper, sync_wrapper

# from shared.abstractions import EntityLevel


# from ..models import (
#     WrappedKGCommunitiesResponse,
#     WrappedKGCreationResponse,
#     WrappedKGEntityDeduplicationResponse,
#     WrappedKGTunePromptResponse,
# )


class GraphsSDK:
    """
    SDK for interacting with knowledge graphs in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        collection_id: Union[str, UUID],
        settings: Optional[Dict[str, Any]] = None,
        run_with_orchestration: Optional[bool] = True,
    ):  # -> WrappedKGCreationResponse:
        """
        Create a new knowledge graph for a collection.

        Args:
            collection_id (Union[str, UUID]): Collection ID to create graph for
            settings (Optional[Dict[str, Any]]): Graph creation settings
            run_with_orchestration (Optional[bool]): Whether to run with task orchestration

        Returns:
            WrappedKGCreationResponse: Creation results
        """
        params = {"run_with_orchestration": run_with_orchestration}
        data = {}
        if settings:
            data["settings"] = settings

        return await self.client._make_request(
            "POST", f"graphs/{str(collection_id)}", json=data, params=params
        )

    async def get_status(self, collection_id: Union[str, UUID]) -> dict:
        """
        Get the status of a graph.

        Args:
            collection_id (Union[str, UUID]): Collection ID to get graph status for

        Returns:
            dict: Graph status information
        """
        return await self.client._make_request(
            "GET", f"graphs/{str(collection_id)}"
        )

    async def delete(
        self, collection_id: Union[str, UUID], cascade: bool = False
    ) -> dict:
        """
        Delete a graph.

        Args:
            collection_id (Union[str, UUID]): Collection ID of graph to delete
            cascade (bool): Whether to delete associated entities and relationships

        Returns:
            dict: Deletion confirmation
        """
        params = {"cascade": cascade}
        return await self.client._make_request(
            "DELETE", f"graphs/{str(collection_id)}", params=params
        )

    # Entity operations
    async def create_entity(
        self, collection_id: Union[str, UUID], entity: Dict[str, Any]
    ) -> dict:
        """
        Create a new entity in the graph.

        Args:
            collection_id (Union[str, UUID]): Collection ID to create entity in
            entity (Dict[str, Any]): Entity data including name, type, and metadata

        Returns:
            dict: Created entity information
        """
        return await self.client._make_request(
            "POST", f"graphs/{str(collection_id)}/entities", json=entity
        )

    async def get_entity(
        self,
        collection_id: Union[str, UUID],
        entity_id: Union[str, UUID],
        include_embeddings: bool = False,
    ) -> dict:
        """
        Get details of a specific entity.

        Args:
            collection_id (Union[str, UUID]): Collection ID containing the entity
            entity_id (Union[str, UUID]): Entity ID to retrieve
            include_embeddings (bool): Whether to include vector embeddings

        Returns:
            dict: Entity details
        """
        params = {"include_embeddings": include_embeddings}
        return await self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/entities/{str(entity_id)}",
            params=params,
        )

    async def update_entity(
        self,
        collection_id: Union[str, UUID],
        entity_id: Union[str, UUID],
        entity_update: Dict[str, Any],
    ) -> dict:
        """
        Update an existing entity.

        Args:
            collection_id (Union[str, UUID]): Collection ID containing the entity
            entity_id (Union[str, UUID]): Entity ID to update
            entity_update (Dict[str, Any]): Updated entity data

        Returns:
            dict: Updated entity information
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/entities/{str(entity_id)}",
            json=entity_update,
        )

    async def delete_entity(
        self,
        collection_id: Union[str, UUID],
        entity_id: Union[str, UUID],
        cascade: bool = False,
    ) -> dict:
        """
        Delete an entity.

        Args:
            collection_id (Union[str, UUID]): Collection ID containing the entity
            entity_id (Union[str, UUID]): Entity ID to delete
            cascade (bool): Whether to delete related relationships

        Returns:
            dict: Deletion confirmation
        """
        params = {"cascade": cascade}
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/entities/{str(entity_id)}",
            params=params,
        )

    async def list_entities(
        self,
        collection_id: Union[str, UUID],
        level,  # : EntityLevel = EntityLevel.DOCUMENT,
        offset: int = 0,
        limit: int = 100,
        include_embeddings: bool = False,
    ) -> dict:
        """
        List entities in the graph.

        Args:
            collection_id (Union[str, UUID]): Collection ID to list entities from
            level (EntityLevel): Entity level filter
            offset (int): Pagination offset
            limit (int): Maximum number of entities to return
            include_embeddings (bool): Whether to include vector embeddings

        Returns:
            dict: List of entities and pagination information
        """
        params = {
            "level": level,
            "offset": offset,
            "limit": limit,
            "include_embeddings": include_embeddings,
        }
        return await self.client._make_request(
            "GET", f"graphs/{str(collection_id)}/entities", params=params
        )

    async def deduplicate_entities(
        self,
        collection_id: Union[str, UUID],
        settings: Optional[Dict[str, Any]] = None,
        run_type: str = "ESTIMATE",
        run_with_orchestration: bool = True,
    ):  # -> WrappedKGEntityDeduplicationResponse:
        """
        Deduplicate entities in the graph.

        Args:
            collection_id (Union[str, UUID]): Collection ID to deduplicate entities in
            settings (Optional[Dict[str, Any]]): Deduplication settings
            run_type (str): Whether to estimate cost or run deduplication
            run_with_orchestration (bool): Whether to run with task orchestration

        Returns:
            WrappedKGEntityDeduplicationResponse: Deduplication results or cost estimate
        """
        params = {
            "run_type": run_type,
            "run_with_orchestration": run_with_orchestration,
        }
        data = {}
        if settings:
            data["settings"] = settings

        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/entities/deduplicate",
            json=data,
            params=params,
        )

    # Relationship operations
    async def create_relationship(
        self, collection_id: Union[str, UUID], relationship: Dict[str, Any]
    ) -> dict:
        """
        Create a new relationship between entities.

        Args:
            collection_id (Union[str, UUID]): Collection ID to create relationship in
            relationship (Dict[str, Any]): Relationship data including source, target, and type

        Returns:
            dict: Created relationship information
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/relationships",
            json=relationship,
        )

    async def get_relationship(
        self,
        collection_id: Union[str, UUID],
        relationship_id: Union[str, UUID],
    ) -> dict:
        """
        Get details of a specific relationship.

        Args:
            collection_id (Union[str, UUID]): Collection ID containing the relationship
            relationship_id (Union[str, UUID]): Relationship ID to retrieve

        Returns:
            dict: Relationship details
        """
        return await self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/relationships/{str(relationship_id)}",
        )

    async def update_relationship(
        self,
        collection_id: Union[str, UUID],
        relationship_id: Union[str, UUID],
        relationship_update: Dict[str, Any],
    ) -> dict:
        """
        Update an existing relationship.

        Args:
            collection_id (Union[str, UUID]): Collection ID containing the relationship
            relationship_id (Union[str, UUID]): Relationship ID to update
            relationship_update (Dict[str, Any]): Updated relationship data

        Returns:
            dict: Updated relationship information
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/relationships/{str(relationship_id)}",
            json=relationship_update,
        )

    async def delete_relationship(
        self,
        collection_id: Union[str, UUID],
        relationship_id: Union[str, UUID],
    ) -> dict:
        """
        Delete a relationship.

        Args:
            collection_id (Union[str, UUID]): Collection ID containing the relationship
            relationship_id (Union[str, UUID]): Relationship ID to delete

        Returns:
            dict: Deletion confirmation
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/relationships/{str(relationship_id)}",
        )

    async def list_relationships(
        self,
        collection_id: Union[str, UUID],
        source_id: Optional[Union[str, UUID]] = None,
        target_id: Optional[Union[str, UUID]] = None,
        relationship_type: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        """
        List relationships in the graph.

        Args:
            collection_id (Union[str, UUID]): Collection ID to list relationships from
            source_id (Optional[Union[str, UUID]]): Filter by source entity
            target_id (Optional[Union[str, UUID]]): Filter by target entity
            relationship_type (Optional[str]): Filter by relationship type
            offset (int): Pagination offset
            limit (int): Maximum number of relationships to return

        Returns:
            dict: List of relationships and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
        }
        if source_id:
            params["source_id"] = str(source_id)
        if target_id:
            params["target_id"] = str(target_id)
        if relationship_type:
            params["relationship_type"] = relationship_type

        return await self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/relationships",
            params=params,
        )

    # Community operations
    async def create_communities(
        self,
        collection_id: Union[str, UUID],
        settings: Optional[Dict[str, Any]] = None,
        run_with_orchestration: bool = True,
    ):  # -> WrappedKGCommunitiesResponse:
        """
        Create communities in the graph.

        Args:
            collection_id (Union[str, UUID]): Collection ID to create communities in
            settings (Optional[Dict[str, Any]]): Community detection settings
            run_with_orchestration (bool): Whether to run with task orchestration

        Returns:
            WrappedKGCommunitiesResponse: Community creation results
        """
        params = {"run_with_orchestration": run_with_orchestration}
        data = {}
        if settings:
            data["settings"] = settings

        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/communities",
            json=data,
            params=params,
        )

    async def get_community(
        self,
        collection_id: Union[str, UUID],
        community_id: Union[str, UUID],
    ) -> dict:
        """
        Get details of a specific community.

        Args:
            collection_id (Union[str, UUID]): Collection ID containing the community
            community_id (Union[str, UUID]): Community ID to retrieve

        Returns:
            dict: Community details
        """
        return await self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
        )

    async def update_community(
        self,
        collection_id: Union[str, UUID],
        community_id: Union[str, UUID],
        community_update: Dict[str, Any],
    ) -> dict:
        """
        Update a community.

        Args:
            collection_id (Union[str, UUID]): Collection ID containing the community
            community_id (Union[str, UUID]): Community ID to update
            community_update (Dict[str, Any]): Updated community data

        Returns:
            dict: Updated community information
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
            json=community_update,
        )

    async def list_communities(
        self,
        collection_id: Union[str, UUID],
        level: Optional[int] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        """
        List communities in the graph.

        Args:
            collection_id (Union[str, UUID]): Collection ID to list communities from
            level (Optional[int]): Filter by community level
            offset (int): Pagination offset
            limit (int): Maximum number of communities to return

        Returns:
            dict: List of communities and pagination information
        """
        params = {
            "offset": offset,
            "limit": limit,
        }
        if level is not None:
            params["level"] = level

        return await self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/communities",
            params=params,
        )

    async def delete_community(
        self,
        collection_id: Union[str, UUID],
        community_id: Union[str, UUID],
    ) -> dict:
        """
        Delete a specific community.

        Args:
            collection_id (Union[str, UUID]): Collection ID containing the community
            community_id (Union[str, UUID]): Community ID to delete

        Returns:
            dict: Deletion confirmation
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
        )

    async def delete_communities(
        self,
        collection_id: Union[str, UUID],
        level: Optional[int] = None,
    ) -> dict:
        """
        Delete communities from the graph.

        Args:
            collection_id (Union[str, UUID]): Collection ID to delete communities from
            level (Optional[int]): Specific level to delete, or None for all levels

        Returns:
            dict: Deletion confirmation
        """
        params = {}
        if level is not None:
            params["level"] = level

        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/communities",
            params=params,
        )

    async def tune_prompt(
        self,
        collection_id: Union[str, UUID],
        prompt_name: str,
        documents_offset: int = 0,
        documents_limit: int = 100,
        chunks_offset: int = 0,
        chunks_limit: int = 100,
    ):  # -> WrappedKGTunePromptResponse:
        """
        Tune a graph-related prompt using collection data.

        Args:
            collection_id (Union[str, UUID]): Collection ID to tune prompt for
            prompt_name (str): Name of prompt to tune (kg_triples_extraction_prompt,
                             kg_entity_description_prompt, or community_reports_prompt)
            documents_offset (int): Document pagination offset
            documents_limit (int): Maximum number of documents to use
            chunks_offset (int): Chunk pagination offset
            chunks_limit (int): Maximum number of chunks to use

        Returns:
            WrappedKGTunePromptResponse: Tuned prompt results
        """
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
        )


class SyncGraphsSDK:
    """Synchronous wrapper for GraphsSDK"""

    def __init__(self, async_sdk: GraphsSDK):
        self._async_sdk = async_sdk

        # Get all attributes from the async SDK instance
        for name in dir(async_sdk):
            if not name.startswith("_"):  # Skip private methods
                attr = getattr(async_sdk, name)
                # Check if it's a method and if it's async
                if callable(attr) and (
                    iscoroutinefunction(attr) or isasyncgenfunction(attr)
                ):
                    if isasyncgenfunction(attr):
                        setattr(self, name, sync_generator_wrapper(attr))
                    else:
                        setattr(self, name, sync_wrapper(attr))
