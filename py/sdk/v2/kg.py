from typing import Optional, Union
from uuid import UUID

from ..models import (
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEntityDeduplicationSettings,
    KGRunType,
)


class KGMixins:
    async def create_graph(
        self,
        collection_id: Optional[Union[UUID, str]] = None,
        run_type: Optional[Union[str, KGRunType]] = None,
        kg_creation_settings: Optional[Union[dict, KGCreationSettings]] = None,
        run_with_orchestration: Optional[bool] = None,
    ) -> dict:
        """
        Create a graph from the given settings.

        Args:
            collection_id (Optional[Union[UUID, str]]): The ID of the collection to create the graph for.
            run_type (Optional[Union[str, KGRunType]]): The type of run to perform.
            kg_creation_settings (Optional[Union[dict, KGCreationSettings]]): Settings for the graph creation process.
        """
        if isinstance(kg_creation_settings, KGCreationSettings):
            kg_creation_settings = kg_creation_settings.model_dump()

        data = {
            "collection_id": str(collection_id) if collection_id else None,
            "run_type": str(run_type) if run_type else None,
            "kg_creation_settings": kg_creation_settings or {},
            "run_with_orchestration": run_with_orchestration or True,
        }

        return await self._make_request("POST", "create_graph", json=data)  # type: ignore

    async def enrich_graph(
        self,
        collection_id: Optional[Union[UUID, str]] = None,
        run_type: Optional[Union[str, KGRunType]] = None,
        kg_enrichment_settings: Optional[
            Union[dict, KGEnrichmentSettings]
        ] = None,
        run_with_orchestration: Optional[bool] = None,
    ) -> dict:
        """
        Perform graph enrichment over the entire graph.

        Args:
            collection_id (Optional[Union[UUID, str]]): The ID of the collection to enrich the graph for.
            run_type (Optional[Union[str, KGRunType]]): The type of run to perform.
            kg_enrichment_settings (Optional[Union[dict, KGEnrichmentSettings]]): Settings for the graph enrichment process.
        Returns:
            Results of the graph enrichment process.
        """
        if isinstance(kg_enrichment_settings, KGEnrichmentSettings):
            kg_enrichment_settings = kg_enrichment_settings.model_dump()

        data = {
            "collection_id": str(collection_id) if collection_id else None,
            "run_type": str(run_type) if run_type else None,
            "kg_enrichment_settings": kg_enrichment_settings or {},
            "run_with_orchestration": run_with_orchestration or True,
        }

        return await self._make_request("POST", "enrich_graph", json=data)  # type: ignore

    async def get_entities(
        self,
        collection_id: Optional[Union[UUID, str]] = None,
        entity_level: Optional[str] = None,
        entity_ids: Optional[list[str]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Retrieve entities from the knowledge graph.

        Args:
            collection_id (str): The ID of the collection to retrieve entities from.
            offset (int): The offset for pagination.
            limit (int): The limit for pagination.
            entity_level (Optional[str]): The level of entity to filter by.
            entity_ids (Optional[List[str]]): Optional list of entity IDs to filter by.

        Returns:
            dict: A dictionary containing the retrieved entities and total count.
        """

        params = {
            "collection_id": collection_id,
            "entity_level": entity_level,
            "entity_ids": entity_ids,
            "offset": offset,
            "limit": limit,
        }

        params = {k: v for k, v in params.items() if v is not None}

        return await self._make_request("GET", "entities", params=params)  # type: ignore

    async def get_triples(
        self,
        collection_id: Optional[Union[UUID, str]] = None,
        entity_names: Optional[list[str]] = None,
        relationship_ids: Optional[list[str]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Retrieve relationships from the knowledge graph.

        Args:
            collection_id (str): The ID of the collection to retrieve relationships from.
            offset (int): The offset for pagination.
            limit (int): The limit for pagination.
            entity_names (Optional[List[str]]): Optional list of entity names to filter by.
            relationship_ids (Optional[List[str]]): Optional list of relationship IDs to filter by.

        Returns:
            dict: A dictionary containing the retrieved relationships and total count.
        """

        params = {
            "collection_id": collection_id,
            "entity_names": entity_names,
            "relationship_ids": relationship_ids,
            "offset": offset,
            "limit": limit,
        }

        params = {k: v for k, v in params.items() if v is not None}

        return await self._make_request("GET", "relationships", params=params)  # type: ignore

    async def get_communities(
        self,
        collection_id: Optional[Union[UUID, str]] = None,
        levels: Optional[list[int]] = None,
        community_ids: Optional[list[UUID]] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> dict:
        """
        Retrieve communities from the knowledge graph.

        Args:
            collection_id (str): The ID of the collection to retrieve communities from.
            offset (int): The offset for pagination.
            limit (int): The limit for pagination.
            levels (Optional[List[int]]): Optional list of levels to filter by.
            community_ids (Optional[List[int]]): Optional list of community numbers to filter by.

        Returns:
            dict: A dictionary containing the retrieved communities.
        """

        params = {
            "collection_id": collection_id,
            "levels": levels,
            "community_ids": community_ids,
            "offset": offset,
            "limit": limit,
        }

        params = {k: v for k, v in params.items() if v is not None}

        return await self._make_request("GET", "communities", params=params)  # type: ignore

    async def get_tuned_prompt(
        self,
        prompt_name: str,
        collection_id: Optional[str] = None,
        documents_offset: Optional[int] = 0,
        documents_limit: Optional[int] = 100,
        chunk_offset: Optional[int] = 0,
        chunk_limit: Optional[int] = 100,
    ) -> dict:
        """
        Tune the GraphRAG prompt for a given collection.

        The tuning process provides an LLM with chunks from each document in the collection. The relative sample size can therefore be controlled by adjusting the document and chunk limits.

        Args:
            prompt_name (str): The name of the prompt to tune.
            collection_id (str): The ID of the collection to tune the prompt for.
            documents_offset (Optional[int]): The offset for pagination of documents.
            documents_limit (Optional[int]): The limit for pagination of documents.
            chunk_offset (Optional[int]): The offset for pagination of chunks.
            chunk_limit (Optional[int]): The limit for pagination of chunks.

        Returns:
            dict: A dictionary containing the tuned prompt.
        """
        params = {
            "prompt_name": prompt_name,
            "collection_id": collection_id,
            "documents_offset": documents_offset,
            "documents_limit": documents_limit,
            "chunk_offset": chunk_offset,
            "chunk_limit": chunk_limit,
        }

        params = {k: v for k, v in params.items() if v is not None}

        return await self._make_request("GET", "tuned_prompt", params=params)  # type: ignore

    async def deduplicate_entities(
        self,
        collection_id: Optional[Union[UUID, str]] = None,
        run_type: Optional[Union[str, KGRunType]] = None,
        deduplication_settings: Optional[
            Union[dict, KGEntityDeduplicationSettings]
        ] = None,
    ):
        """
        Deduplicate entities in the knowledge graph.
        Args:
            collection_id (Optional[Union[UUID, str]]): The ID of the collection to deduplicate entities for.
            run_type (Optional[Union[str, KGRunType]]): The type of run to perform.
            deduplication_settings (Optional[Union[dict, KGEntityDeduplicationSettings]]): Settings for the deduplication process.
        """
        if isinstance(deduplication_settings, KGEntityDeduplicationSettings):
            deduplication_settings = deduplication_settings.model_dump()

        data = {
            "collection_id": str(collection_id) if collection_id else None,
            "run_type": str(run_type) if run_type else None,
            "deduplication_settings": deduplication_settings or {},
        }

        return await self._make_request(  # type: ignore
            "POST", "deduplicate_entities", json=data
        )

    async def delete_graph_for_collection(
        self, collection_id: Union[UUID, str], cascade: bool = False
    ) -> dict:
        """
        Delete the graph for a given collection.

        Args:
            collection_id (Union[UUID, str]): The ID of the collection to delete the graph for.
            cascade (bool): Whether to cascade the deletion, and delete entities and relationships belonging to the collection.

            NOTE: Setting this flag to true will delete entities and relationships for documents that are shared across multiple collections. Do not set this flag unless you are absolutely sure that you want to delete the entities and relationships for all documents in the collection.
        """

        data = {
            "collection_id": str(collection_id),
            "cascade": cascade,
        }

        return await self._make_request("DELETE", "delete_graph_for_collection", json=data)  # type: ignore
