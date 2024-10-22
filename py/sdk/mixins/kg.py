from typing import Optional, Union
from uuid import UUID

from ..models import (
    KGCreationSettings,
    KGEnrichmentSettings,
    KGEntityDeduplicationResponse,
    KGEntityDeduplicationSettings,
    KGRunType,
)


class KGMixins:
    async def create_graph(
        self,
        collection_id: Optional[Union[UUID, str]] = None,
        run_type: Optional[Union[str, KGRunType]] = None,
        kg_creation_settings: Optional[Union[dict, KGCreationSettings]] = None,
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
        }

        return await self._make_request("POST", "create_graph", json=data)  # type: ignore

    async def enrich_graph(
        self,
        collection_id: Optional[Union[UUID, str]] = None,
        run_type: Optional[Union[str, KGRunType]] = None,
        kg_enrichment_settings: Optional[
            Union[dict, KGEnrichmentSettings]
        ] = None,
    ) -> dict:
        """
        Perform graph enrichment over the entire graph.

        Args:
            collection_id (Optional[Union[UUID, str]]): The ID of the collection to enrich the graph for.
            run_type (Optional[Union[str, KGRunType]]): The type of run to perform.
            kg_enrichment_settings (Optional[Union[dict, KGEnrichmentSettings]]): Settings for the graph enrichment process.
        Returns:
            KGEnrichmentResponse: Results of the graph enrichment process.
        """
        if isinstance(kg_enrichment_settings, KGEnrichmentSettings):
            kg_enrichment_settings = kg_enrichment_settings.model_dump()

        data = {
            "collection_id": str(collection_id) if collection_id else None,
            "run_type": str(run_type) if run_type else None,
            "kg_enrichment_settings": kg_enrichment_settings or {},
        }

        return await self._make_request("POST", "enrich_graph", json=data)  # type: ignore

    async def get_entities(
        self,
        collection_id: str,
        offset: int = 0,
        limit: int = 100,
        entity_level: Optional[str] = "collection",
        entity_ids: Optional[list[str]] = None,
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
            "entity_level": entity_level,
            "collection_id": collection_id,
            "offset": offset,
            "limit": limit,
        }
        if entity_ids:
            params["entity_ids"] = ",".join(entity_ids)

        return await self._make_request("GET", "entities", params=params)  # type: ignore

    async def get_triples(
        self,
        collection_id: str,
        offset: int = 0,
        limit: int = 100,
        entity_names: Optional[list[str]] = None,
        triple_ids: Optional[list[str]] = None,
    ) -> dict:
        """
        Retrieve triples from the knowledge graph.

        Args:
            collection_id (str): The ID of the collection to retrieve triples from.
            offset (int): The offset for pagination.
            limit (int): The limit for pagination.
            entity_names (Optional[List[str]]): Optional list of entity names to filter by.
            triple_ids (Optional[List[str]]): Optional list of triple IDs to filter by.

        Returns:
            dict: A dictionary containing the retrieved triples and total count.
        """
        params = {
            "collection_id": collection_id,
            "offset": offset,
            "limit": limit,
        }

        if entity_names:
            params["entity_names"] = entity_names

        if triple_ids:
            params["triple_ids"] = ",".join(triple_ids)

        return await self._make_request("GET", "triples", params=params)  # type: ignore

    async def get_communities(
        self,
        collection_id: str,
        offset: int = 0,
        limit: int = 100,
        levels: Optional[list[int]] = None,
        community_numbers: Optional[list[int]] = None,
    ) -> dict:
        """
        Retrieve communities from the knowledge graph.

        Args:
            collection_id (str): The ID of the collection to retrieve communities from.
            offset (int): The offset for pagination.
            limit (int): The limit for pagination.
            levels (Optional[List[int]]): Optional list of levels to filter by.
            community_numbers (Optional[List[int]]): Optional list of community numbers to filter by.

        Returns:
            dict: A dictionary containing the retrieved communities.
        """
        params = {
            "collection_id": collection_id,
            "offset": offset,
            "limit": limit,
        }

        if levels:
            params["levels"] = levels
        if community_numbers:
            params["community_numbers"] = community_numbers

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
    ) -> KGEntityDeduplicationResponse:
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
