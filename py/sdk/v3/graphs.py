from typing import Optional
from uuid import UUID

from core.base.abstractions import DataLevel, KGRunType

from ..models import KGCreationSettings, KGRunType


class GraphsSDK:
    """
    SDK for interacting with knowledge graphs in the v3 API.
    """

    def __init__(self, client):
        self.client = client

    async def create(
        self,
        collection_id: str | UUID,
        run_type: Optional[str | KGRunType] = None,
        settings: Optional[dict | KGCreationSettings] = None,
        run_with_orchestration: Optional[bool] = True,
    ):
        """
        Create a new knowledge graph for a collection.

        Args:
            collection_id (str | UUID): Collection ID to create graph for
            settings (Optional[dict]): Graph creation settings
            run_with_orchestration (Optional[bool]): Whether to run with task orchestration

        Returns:
            WrappedKGCreationResponse: Creation results
        """
        if isinstance(settings, KGCreationSettings):
            settings = settings.model_dump()

        data = {
            # "collection_id": str(collection_id) if collection_id else None,
            "run_type": str(run_type) if run_type else None,
            "settings": settings or {},
            "run_with_orchestration": run_with_orchestration or True,
        }

        return await self.client._make_request("POST", f"graphs/{collection_id}", json=data)  # type: ignore

    async def get_status(self, collection_id: str | UUID) -> dict:
        """
        Get the status of a graph.

        Args:
            collection_id (str | UUID): Collection ID to get graph status for

        Returns:
            dict: Graph status information
        """
        return await self.client._make_request(
            "GET", f"graphs/{str(collection_id)}"
        )

    async def delete(
        self,
        collection_id: str | UUID,
        cascade: bool = False,
    ) -> dict:
        """
        Delete a graph.

        Args:
            collection_id (str | UUID): Collection ID of graph to delete
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
        self,
        collection_id: str | UUID,
        entity: dict,
    ) -> dict:
        """
        Create a new entity in the graph.

        Args:
            collection_id (str | UUID): Collection ID to create entity in
            entity (dict): Entity data including name, type, and metadata

        Returns:
            dict: Created entity information
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/entities",
            json=entity,
            version="v3",
        )

    async def get_entity(
        self,
        collection_id: str | UUID,
        entity_id: str | int,
        include_embeddings: bool = False,
    ) -> dict:
        """
        Get details of a specific entity.

        Args:
            collection_id (str | UUID): Collection ID containing the entity
            entity_id (str | UUID): Entity ID to retrieve
            include_embeddings (bool): Whether to include vector embeddings

        Returns:
            dict: Entity details
        """
        params = {"include_embeddings": include_embeddings}
        return await self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/entities/{str(entity_id)}",
            params=params,
            version="v3",
        )

    async def update_entity(
        self,
        collection_id: str | UUID,
        entity_id: str | UUID,
        entity_update: dict,
    ) -> dict:
        """
        Update an existing entity.

        Args:
            collection_id (str | UUID): Collection ID containing the entity
            entity_id (str | UUID): Entity ID to update
            entity_update (dict): Updated entity data

        Returns:
            dict: Updated entity information
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/entities/{str(entity_id)}",
            json=entity_update,
            version="v3",
        )

    async def delete_entity(
        self,
        collection_id: str | UUID,
        entity_id: str | UUID,
        cascade: bool = False,
    ) -> dict:
        """
        Delete an entity.

        Args:
            collection_id (str | UUID): Collection ID containing the entity
            entity_id (str | UUID): Entity ID to delete
            cascade (bool): Whether to delete related relationships

        Returns:
            dict: Deletion confirmation
        """
        params = {"cascade": cascade}
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/entities/{str(entity_id)}",
            params=params,
            version="v3",
        )

    async def list_entities(
        self,
        collection_id: str | UUID,
        level=DataLevel.DOCUMENT,
        include_embeddings: bool = False,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> dict:
        """
        List entities in the graph.

        Args:
            collection_id (str | UUID): Collection ID to list entities from
            level (DataLevel): Entity level filter
            include_embeddings (bool): Whether to include vector embeddings
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

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
            "GET",
            f"graphs/{str(collection_id)}/entities",
            params=params,
            version="v3",
        )

    async def deduplicate_entities(
        self,
        collection_id: str | UUID,
        settings: Optional[dict] = None,
        run_type: str = "ESTIMATE",
        run_with_orchestration: bool = True,
    ):
        """
        Deduplicate entities in the graph.

        Args:
            collection_id (str | UUID): Collection ID to deduplicate entities in
            settings (Optional[dict]): Deduplication settings
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
            version="v3",
        )

    # Relationship operations
    async def create_relationship(
        self, collection_id: str | UUID, relationship: dict
    ) -> dict:
        """
        Create a new relationship between entities.

        Args:
            collection_id (str | UUID): Collection ID to create relationship in
            relationship (dict): Relationship data including source, target, and type

        Returns:
            dict: Created relationship information
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/relationships",
            json=relationship,
            version="v3",
        )

    async def get_relationship(
        self,
        collection_id: str | UUID,
        relationship_id: str | UUID,
    ) -> dict:
        """
        Get details of a specific relationship.

        Args:
            collection_id (str | UUID): Collection ID containing the relationship
            relationship_id (str | UUID): Relationship ID to retrieve

        Returns:
            dict: Relationship details
        """
        return await self.client._make_request(
            "GET",
            f"graphs/{str(collection_id)}/relationships/{str(relationship_id)}",
            version="v3",
        )

    async def update_relationship(
        self,
        collection_id: str | UUID,
        relationship_id: str | UUID,
        relationship_update: dict,
    ) -> dict:
        """
        Update an existing relationship.

        Args:
            collection_id (str | UUID): Collection ID containing the relationship
            relationship_id (str | UUID): Relationship ID to update
            relationship_update (dict): Updated relationship data

        Returns:
            dict: Updated relationship information
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/relationships/{str(relationship_id)}",
            json=relationship_update,
            version="v3",
        )

    async def delete_relationship(
        self,
        collection_id: str | UUID,
        relationship_id: str | UUID,
    ) -> dict:
        """
        Delete a relationship.

        Args:
            collection_id (str | UUID): Collection ID containing the relationship
            relationship_id (str | UUID): Relationship ID to delete

        Returns:
            dict: Deletion confirmation
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/relationships/{str(relationship_id)}",
            version="v3",
        )

    async def list_relationships(
        self,
        collection_id: str | UUID,
        source_id: Optional[str | UUID] = None,
        target_id: Optional[str | UUID] = None,
        relationship_type: Optional[str] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> dict:
        """
        List relationships in the graph.

        Args:
            collection_id (str | UUID): Collection ID to list relationships from
            source_id (Optional[str | UUID]): Filter by source entity
            target_id (Optional[str | UUID]): Filter by target entity
            relationship_type (Optional[str]): Filter by relationship type
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

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
            version="v3",
        )

    # Community operations
    async def create_communities(
        self,
        collection_id: str | UUID,
        run_type: Optional[str | KGRunType] = None,
        settings: Optional[dict] = None,
        run_with_orchestration: bool = True,
    ):  # -> WrappedKGCommunitiesResponse:
        """
        Create communities in the graph.

        Args:
            collection_id (str | UUID): Collection ID to create communities in
            settings (Optional[dict]): Community detection settings
            run_with_orchestration (bool): Whether to run with task orchestration

        Returns:
            WrappedKGCommunitiesResponse: Community creation results
        """
        params = {"run_with_orchestration": run_with_orchestration}
        data = {}
        if settings:
            data["settings"] = settings

        if run_type:
            data["run_type"] = str(run_type)

        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/communities",
            json=data,
            params=params,
            version="v3",
        )

    async def get_community(
        self,
        collection_id: str | UUID,
        community_id: str | UUID,
    ) -> dict:
        """
        Get details of a specific community.

        Args:
            collection_id (str | UUID): Collection ID containing the community
            community_id (str | UUID): Community ID to retrieve

        Returns:
            dict: Community details
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
        community_update: dict,
    ) -> dict:
        """
        Update a community.

        Args:
            collection_id (str | UUID): Collection ID containing the community
            community_id (str | UUID): Community ID to update
            community_update (dict): Updated community data

        Returns:
            dict: Updated community information
        """
        return await self.client._make_request(
            "POST",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
            json=community_update,
            version="v3",
        )

    async def list_communities(
        self,
        collection_id: str | UUID,
        level: Optional[int] = None,
        offset: Optional[int] = 0,
        limit: Optional[int] = 100,
    ) -> dict:
        """
        List communities in the graph.

        Args:
            collection_id (str | UUID): Collection ID to list communities from
            level (Optional[int]): Filter by community level
            offset (int, optional): Specifies the number of objects to skip. Defaults to 0.
            limit (int, optional): Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.

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
            version="v3",
        )

    async def delete_community(
        self,
        collection_id: str | UUID,
        community_id: str | UUID,
    ) -> dict:
        """
        Delete a specific community.

        Args:
            collection_id (str | UUID): Collection ID containing the community
            community_id (str | UUID): Community ID to delete

        Returns:
            dict: Deletion confirmation
        """
        return await self.client._make_request(
            "DELETE",
            f"graphs/{str(collection_id)}/communities/{str(community_id)}",
            version="v3",
        )

    async def delete_communities(
        self,
        collection_id: str | UUID,
        level: Optional[int] = None,
    ) -> dict:
        """
        Delete communities from the graph.

        Args:
            collection_id (str | UUID): Collection ID to delete communities from
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
