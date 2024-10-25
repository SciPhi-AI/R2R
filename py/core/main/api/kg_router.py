import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

import yaml
from fastapi import Body, Depends, Query

from core.base import RunType
from core.base.api.models import (
    WrappedKGCommunitiesResponse,
    WrappedKGCreationResponse,
    WrappedKGEnrichmentResponse,
    WrappedKGEntitiesResponse,
    WrappedKGEntityDeduplicationResponse,
    WrappedKGTriplesResponse,
    WrappedKGTunePromptResponse,
)
from core.base.providers import OrchestrationProvider, Workflow
from core.utils import generate_default_user_collection_id
from shared.abstractions.graph import EntityLevel, Entity, Triple
from shared.abstractions.kg import KGRunType
from shared.utils.base_utils import update_settings_from_dict

from ..services.kg_service import KgService
from core.base.abstractions import CommunityReport
from .base_router import BaseRouter

logger = logging.getLogger()


class KGRouter(BaseRouter):
    def __init__(
        self,
        service: KgService,
        orchestration_provider: Optional[OrchestrationProvider] = None,
        run_type: RunType = RunType.KG,
    ):
        if not orchestration_provider:
            raise ValueError("KGRouter requires an orchestration provider.")
        super().__init__(service, orchestration_provider, run_type)
        self.service: KgService = service

    def _load_openapi_extras(self):
        yaml_path = Path(__file__).parent / "data" / "kg_router_openapi.yml"
        with open(yaml_path, "r") as yaml_file:
            yaml_content = yaml.safe_load(yaml_file)
        return yaml_content

    def _register_workflows(self):

        workflow_messages = {}
        if self.orchestration_provider.config.provider == "hatchet":
            workflow_messages["create-graph"] = (
                "Graph creation task queued successfully."
            )
            workflow_messages["enrich-graph"] = (
                "Graph enrichment task queued successfully."
            )
            workflow_messages["entity-deduplication"] = (
                "KG Entity Deduplication task queued successfully."
            )
        else:
            workflow_messages["create-graph"] = (
                "Graph created successfully, please run enrich-graph to enrich the graph for GraphRAG."
            )
            workflow_messages["enrich-graph"] = (
                "Graph enriched successfully. You can view the communities at http://localhost:7272/v2/communities"
            )
            workflow_messages["entity-deduplication"] = (
                "KG Entity Deduplication completed successfully."
            )

        self.orchestration_provider.register_workflows(
            Workflow.KG,
            self.service,
            workflow_messages,
        )

    def _setup_routes(self):
        @self.router.post(
            "/create_graph",
        )
        @self.base_endpoint
        async def create_graph(
            collection_id: Optional[UUID] = Body(
                default=None,
                description="Collection ID to create graph for.",
            ),
            run_type: Optional[KGRunType] = Body(
                default=None,
                description="Run type for the graph creation process.",
            ),
            kg_creation_settings: Optional[dict] = Body(
                default=None,
                description="Settings for the graph creation process.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGCreationResponse:  # type: ignore
            """
            Creating a graph on your documents. This endpoint takes input a list of document ids and KGCreationSettings.
            If document IDs are not provided, the graph will be created on all documents in the system.
            This step extracts the relevant entities and relationships from the documents and creates a graph based on the extracted information.
            In order to do GraphRAG, you will need to run the enrich_graph endpoint.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            logger.info(f"Running create-graph on collection {collection_id}")

            # If no collection ID is provided, use the default user collection
            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            # If no run type is provided, default to estimate
            if not run_type:
                run_type = KGRunType.ESTIMATE

            # Apply runtime settings overrides
            server_kg_creation_settings = (
                self.service.providers.kg.config.kg_creation_settings
            )

            if kg_creation_settings:
                server_kg_creation_settings = update_settings_from_dict(
                    server_kg_creation_settings, kg_creation_settings
                )

            # If the run type is estimate, return an estimate of the creation cost
            if run_type is KGRunType.ESTIMATE:
                return await self.service.get_creation_estimate(
                    collection_id, server_kg_creation_settings
                )

            # Otherwise, create the graph
            else:
                workflow_input = {
                    "collection_id": str(collection_id),
                    "kg_creation_settings": server_kg_creation_settings.model_dump_json(),
                    "user": auth_user.json(),
                }

                return await self.orchestration_provider.run_workflow(  # type: ignore
                    "create-graph", {"request": workflow_input}, {}
                )

        @self.router.post(
            "/enrich_graph",
        )
        @self.base_endpoint
        async def enrich_graph(
            collection_id: Optional[UUID] = Body(
                default=None,
                description="Collection ID to enrich graph for.",
            ),
            run_type: Optional[KGRunType] = Body(
                default=KGRunType.ESTIMATE,
                description="Run type for the graph enrichment process.",
            ),
            kg_enrichment_settings: Optional[dict] = Body(
                default=None,
                description="Settings for the graph enrichment process.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGEnrichmentResponse:
            """
            This endpoint enriches the graph with additional information.
            It creates communities of nodes based on their similarity and adds embeddings to the graph.
            This step is necessary for GraphRAG to work.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            # If no collection ID is provided, use the default user collection
            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            # If no run type is provided, default to estimate
            if not run_type:
                run_type = KGRunType.ESTIMATE

            # Apply runtime settings overrides
            server_kg_enrichment_settings = (
                self.service.providers.kg.config.kg_enrichment_settings
            )
            if kg_enrichment_settings:
                server_kg_enrichment_settings = update_settings_from_dict(
                    server_kg_enrichment_settings, kg_enrichment_settings
                )

            # If the run type is estimate, return an estimate of the enrichment cost
            if run_type is KGRunType.ESTIMATE:
                return await self.service.get_enrichment_estimate(
                    collection_id, server_kg_enrichment_settings
                )

            # Otherwise, run the enrichment workflow
            else:
                workflow_input = {
                    "collection_id": str(collection_id),
                    "kg_enrichment_settings": server_kg_enrichment_settings.model_dump_json(),
                    "user": auth_user.json(),
                }

                return await self.orchestration_provider.run_workflow(  # type: ignore
                    "enrich-graph", {"request": workflow_input}, {}
                )

        @self.router.get("/entities")
        @self.base_endpoint
        async def get_entities(
            entity_level: Optional[EntityLevel] = Query(
                default=EntityLevel.DOCUMENT,
                description="Type of entities to retrieve. Options are: raw, dedup_document, dedup_collection.",
            ),
            collection_id: Optional[UUID] = Query(
                None, description="Collection ID to retrieve entities from."
            ),
            offset: int = Query(0, ge=0, description="Offset for pagination."),
            limit: int = Query(
                100, ge=1, le=1000, description="Limit for pagination."
            ),
            entity_ids: Optional[list[str]] = Query(
                None, description="Entity IDs to filter by."
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGEntitiesResponse:
            """
            Retrieve entities from the knowledge graph.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            if entity_level == EntityLevel.CHUNK:
                entity_table_name = "chunk_entity"
            elif entity_level == EntityLevel.DOCUMENT:
                entity_table_name = "document_entity"
            else:
                entity_table_name = "collection_entity"

            return await self.service.get_entities(
                collection_id,
                offset,
                limit,
                entity_ids,
                entity_table_name,
            )

        @self.router.get("/triples")
        @self.base_endpoint
        async def get_triples(
            collection_id: Optional[UUID] = Query(
                None, description="Collection ID to retrieve triples from."
            ),
            offset: int = Query(0, ge=0, description="Offset for pagination."),
            limit: int = Query(
                100, ge=1, le=1000, description="Limit for pagination."
            ),
            entity_names: Optional[list[str]] = Query(
                None, description="Entity names to filter by."
            ),
            triple_ids: Optional[list[str]] = Query(
                None, description="Triple IDs to filter by."
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGTriplesResponse:
            """
            Retrieve triples from the knowledge graph.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            return await self.service.get_triples(
                collection_id,
                offset,
                limit,
                entity_names,
                triple_ids,
            )

        @self.router.get("/communities")
        @self.base_endpoint
        async def get_communities(
            collection_id: Optional[UUID] = Query(
                None, description="Collection ID to retrieve communities from."
            ),
            offset: int = Query(0, ge=0, description="Offset for pagination."),
            limit: int = Query(
                100, ge=1, le=1000, description="Limit for pagination."
            ),
            levels: Optional[list[int]] = Query(
                None, description="Levels to filter by."
            ),
            community_numbers: Optional[list[int]] = Query(
                None, description="Community numbers to filter by."
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGCommunitiesResponse:
            """
            Retrieve communities from the knowledge graph.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            return await self.service.get_communities(
                collection_id,
                offset,
                limit,
                levels,
                community_numbers,
            )

        @self.router.post("/deduplicate_entities")
        @self.base_endpoint
        async def deduplicate_entities(
            collection_id: Optional[UUID] = Body(
                None, description="Collection ID to deduplicate entities for."
            ),
            run_type: Optional[KGRunType] = Body(
                None, description="Run type for the deduplication process."
            ),
            deduplication_settings: Optional[dict] = Body(
                None, description="Settings for the deduplication process."
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGEntityDeduplicationResponse:
            """
            Deduplicate entities in the knowledge graph.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            if not run_type:
                run_type = KGRunType.ESTIMATE

            server_deduplication_settings = (
                self.service.providers.kg.config.kg_entity_deduplication_settings
            )

            logger.info(
                f"Server deduplication settings: {server_deduplication_settings}"
            )

            if deduplication_settings:
                server_deduplication_settings = update_settings_from_dict(
                    server_deduplication_settings, deduplication_settings
                )

            logger.info(
                f"Running deduplicate_entities on collection {collection_id}"
            )
            logger.info(f"Input data: {server_deduplication_settings}")

            if run_type == KGRunType.ESTIMATE:
                return await self.service.get_deduplication_estimate(
                    collection_id, server_deduplication_settings
                )

            workflow_input = {
                "collection_id": str(collection_id),
                "run_type": run_type,
                "kg_entity_deduplication_settings": server_deduplication_settings.model_dump_json(),
                "user": auth_user.json(),
            }

            return await self.orchestration_provider.run_workflow(  # type: ignore
                "entity-deduplication", {"request": workflow_input}, {}
            )

        @self.router.get("/tuned_prompt")
        @self.base_endpoint
        async def get_tuned_prompt(
            prompt_name: str = Query(
                ...,
                description="The name of the prompt to tune. Valid options are 'kg_triples_extraction_prompt', 'kg_entity_description_prompt' and 'community_reports_prompt'.",
            ),
            collection_id: Optional[UUID] = Query(
                None, description="Collection ID to retrieve communities from."
            ),
            documents_offset: Optional[int] = Query(
                0, description="Offset for document pagination."
            ),
            documents_limit: Optional[int] = Query(
                100, description="Limit for document pagination."
            ),
            chunks_offset: Optional[int] = Query(
                0, description="Offset for chunk pagination."
            ),
            chunks_limit: Optional[int] = Query(
                100, description="Limit for chunk pagination."
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedKGTunePromptResponse:
            """
            Auto-tune the prompt for a specific collection.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            return await self.service.tune_prompt(
                prompt_name=prompt_name,
                collection_id=collection_id,
                documents_offset=documents_offset,
                documents_limit=documents_limit,
                chunks_offset=chunks_offset,
                chunks_limit=chunks_limit,
            )

        @self.router.delete("/delete_graph_for_collection")
        @self.base_endpoint
        async def delete_graph_for_collection(
            collection_id: UUID = Body(
                ..., description="Collection ID to delete graph for."
            ),
            cascade: bool = Body(
                default=False,
                description="Whether to cascade the deletion, and delete entities and triples belonging to the collection.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            """
            Delete the graph for a given collection. Note that this endpoint may delete a large amount of data created by the KG pipeline, this deletion is irreversible, and recreating the graph may be an expensive operation.

            Notes:
            The endpoint deletes all communities for a given collection. If the cascade flag is set to true, the endpoint also deletes all the entities and triples associated with the collection.

            WARNING: Setting this flag to true will delete entities and triples for documents that are shared across multiple collections. Do not set this flag unless you are absolutely sure that you want to delete the entities and triples for all documents in the collection.

            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            await self.service.delete_graph_for_collection(
                collection_id, cascade
            )

            return {"message": "Graph deleted successfully."}


        # add entities endpoint 
        @self.router.post("/add_entities")
        @self.base_endpoint
        async def add_entities(
            level: EntityLevel = Body(..., description="Level of entities to add."),
            document_ids: Optional[list[UUID]] = Body(None, description="Document IDs to add entities to. All entities must belong to some document."),
            collection_id: Optional[UUID] = Body(None, description="Collection ID to add entities to."),
            entities: Optional[list[Entity]] = Body(None, description="Entities to add to the graph."),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if len(entities) > 1000:
                raise ValueError("Cannot add more than 1000 entities at a time.")

            # validating inputs here
            if level == EntityLevel.DOCUMENT and not document_ids:
                raise ValueError("document_ids must be provided if level is DOCUMENT")
            if level == EntityLevel.COLLECTION and not collection_id:
                raise ValueError("collection_id must be provided if level is COLLECTION")
            if level == EntityLevel.CHUNK and not document_ids:
                raise ValueError("document_ids must be provided if level is CHUNK")
            
            if not entities:
                raise ValueError("entities must be provided")

            # check if entity level is not chunk, then description embedding must be provided
            if level != EntityLevel.CHUNK and not all(entity.description_embedding for entity in entities):
                raise ValueError("description_embedding must be provided for all entities if level is not CHUNK. Please make sure that you construct embeddings with the same embedding model. Please reach out in our discord channel if you need this feature.")
            
            # check if entity level is chunk, then document_ids must be provided
            if level == EntityLevel.CHUNK and not document_ids:
                raise ValueError("document_ids must be provided if level is CHUNK")
            
            # check that ID is not provided for any entity
            if any(entity.id for entity in entities):
                raise ValueError("ID is not allowed to be provided for any entity. It is automatically generated when the entity is added to the graph.")

            pass

        # add triples endpoint
        @self.router.post("/add_triples")
        @self.base_endpoint
        async def add_triples(
            triples: list[Triple],
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if len(triples) > 1000:
                raise ValueError("Cannot add more than 1000 triples at a time.")

            # no checks for triples, as triples is just a single table. Input validation is done via fastapi.

        # update_entities endpoint
        @self.router.put("/update_entities")
        @self.base_endpoint
        async def update_entities(
            level: EntityLevel = Body(..., description="Level of entities to update."),
            document_ids: Optional[list[UUID]] = Body(None, description="Document IDs to update entities for. All entities must belong to some document."),
            collection_id: Optional[UUID] = Body(None, description="Collection ID to update entities for."),
            entities: list[Entity] = Body(..., description="Entities to update in the graph."),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if len(entities) > 1000:
                raise ValueError("Cannot update more than 1000 entities at a time.")

            # same validation as add_entities
            # also need to validate that ID is provided for all entities
            # also need to validate that the entity.id exists in the graph

        # update_triples endpoint
        @self.router.put("/update_triples")
        @self.base_endpoint
        async def update_triples(
            triples: list[Triple],
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if len(triples) > 1000:
                raise ValueError("Cannot update more than 1000 triples at a time.")

            for triple in triples:
                if not triple.id:
                    raise ValueError("ID is required for all triples.")
                

            # check that ID is provided for all triples. We actually don't need to check if the ID exists in the graph, as we can just update the triples with the provided ID.
            # no checks for triples, as triples is just a single table. Input validation is done via fastapi.

        # delete_entities endpoint
        @self.router.delete("/delete_entities")
        @self.base_endpoint
        async def delete_entities(
            level: EntityLevel = Body(..., description="Level of entities to delete."),
            document_ids: Optional[list[UUID]] = Body(None, description="Document IDs to delete entities for. All entities must belong to some document."),
            collection_id: Optional[UUID] = Body(None, description="Collection ID to delete entities for."),
            entity_ids: list[UUID] = Body(..., description="Entity IDs to delete from the graph."),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if len(entity_ids) > 1000:
                raise ValueError("Cannot delete more than 1000 entities at a time.")

            # same validation as add_entities
            # also need to validate that the entity.id exists in the graph

        # delete_triples endpoint
        @self.router.delete("/delete_triples")
        @self.base_endpoint
        async def delete_triples(
            triple_ids: list[int],
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if len(triple_ids) > 1000:
                raise ValueError("Cannot delete more than 1000 triples at a time.")

            # no checks for triples, as triples is just a single table. Input validation is done via fastapi.


        @self.router.post("/add_communities")
        @self.base_endpoint
        async def add_communities():
            raise NotImplementedError("There is no add communities endpoint because communities are created automatically when enriching the graph.")

        # update_communities endpoint
        @self.router.post("/update_communities")
        @self.base_endpoint
        async def update_communities(
            communities: list[CommunityReport],
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if len(communities) > 100:
                raise ValueError("Cannot update more than 100 communities at a time.")

            # make sure that embedding is provided for all communities
            if not all(community.embedding for community in communities):
                raise ValueError("Embedding is required for all communities.")

            # need to validate that the community.id exists in the graph
            for community in communities:
                if not community.id:
                    raise ValueError("ID is required for all communities.")

        # delete_communities endpoint
        @self.router.post("/delete_communities")
        @self.base_endpoint
        async def delete_community(
            collection_id: UUID = Body(..., description="Collection ID to delete communities for."),
            community_numbers: list[int] = Body(..., description="Community numbers to delete."),
            level: int = Body(..., description="Level of communities to delete."),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            """
            Delete communities from the knowledge graph.
            
            This endpoint deletes specified communities from the knowledge graph for a given collection ID and level.
            The communities are identified by their community numbers.
            
            The deletion process includes:
            1. Validating the collection ID exists
            2. Checking that the specified communities exist at the given level
            3. Removing the communities and their associated data (reports, embeddings, etc.)
            4. Cleaning up any orphaned relationships

            Args:
                collection_id: Collection ID to delete communities for.
                community_numbers: Community numbers to delete.
                level: Level of communities to delete.

            Returns:
                A message indicating that the communities were deleted successfully.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")


            if len(community_numbers) > 100:
                raise ValueError("Cannot delete more than 100 communities at a time.")
