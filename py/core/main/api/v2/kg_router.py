import logging
from pathlib import Path
from typing import Optional, Union
from uuid import UUID

import yaml
from fastapi import Body, Depends, Query

from core.base import Workflow
from core.base.abstractions import DataLevel, KGRunType
from core.base.api.models import (
    WrappedCommunitiesResponse,
    WrappedEntitiesResponse,
    WrappedRelationshipsResponse,
    WrappedKGCreationResponse,
    WrappedKGEnrichmentResponse,
    WrappedKGEntityDeduplicationResponse,
    WrappedKGTunePromptResponse,
    WrappedRelationshipsResponse,
)
from core.base.logger.base import RunType
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from core.utils import (
    generate_default_user_collection_id,
    update_settings_from_dict,
)

from ...services.kg_service import KgService
from .base_router import BaseRouter

logger = logging.getLogger()


class KGRouter(BaseRouter):
    def __init__(
        self,
        service: KgService,
        orchestration_provider: Optional[
            Union[HatchetOrchestrationProvider, SimpleOrchestrationProvider]
        ] = None,
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
                "Document entities and relationships extracted successfully. To generate GraphRAG communities, run cluster on the collection this document belongs to."
            )
            workflow_messages["enrich-graph"] = (
                "Graph communities created successfully. You can view the communities at http://localhost:7272/v2/communities"
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
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            """
            Creating a graph on your documents. This endpoint takes input a list of document ids and KGCreationSettings.
            If document IDs are not provided, the graph will be created on all documents in the system.
            This step extracts the relevant entities and relationships from the documents and creates a graph based on the extracted information.
            In order to do GraphRAG, you will need to run the enrich_graph endpoint.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            # If no collection ID is provided, use the default user collection
            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            logger.info(f"Running create-graph on collection {collection_id}")

            # If no run type is provided, default to estimate
            if not run_type:
                run_type = KGRunType.ESTIMATE

            # Apply runtime settings overrides
            server_kg_creation_settings = (
                self.service.providers.database.config.kg_creation_settings
            )

            if kg_creation_settings:
                server_kg_creation_settings = update_settings_from_dict(
                    server_kg_creation_settings, kg_creation_settings
                )

            # If the run type is estimate, return an estimate of the creation cost
            if run_type is KGRunType.ESTIMATE:
                return await self.service.get_creation_estimate(
                    collection_id=collection_id,
                    kg_creation_settings=server_kg_creation_settings,
                )
            else:

                # Otherwise, create the graph
                if run_with_orchestration:
                    workflow_input = {
                        "collection_id": str(collection_id),
                        "kg_creation_settings": server_kg_creation_settings.model_dump_json(),
                        "user": auth_user.json(),
                    }

                    return await self.orchestration_provider.run_workflow(  # type: ignore
                        "create-graph", {"request": workflow_input}, {}
                    )
                else:
                    from core.main.orchestration import simple_kg_factory

                    logger.info("Running create-graph without orchestration.")
                    simple_kg = simple_kg_factory(self.service)
                    await simple_kg["create-graph"](workflow_input)
                    return {
                        "message": "Graph created successfully.",
                        "task_id": None,
                    }

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
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
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
                self.service.providers.database.config.kg_enrichment_settings
            )
            if kg_enrichment_settings:
                server_kg_enrichment_settings = update_settings_from_dict(
                    server_kg_enrichment_settings, kg_enrichment_settings
                )

            # If the run type is estimate, return an estimate of the enrichment cost
            if run_type is KGRunType.ESTIMATE:
                return await self.service.get_enrichment_estimate(
                    collection_id=collection_id,
                    kg_enrichment_settings=server_kg_enrichment_settings,
                )

            # Otherwise, run the enrichment workflow
            else:
                if run_with_orchestration:
                    workflow_input = {
                        "collection_id": str(collection_id),
                        "kg_enrichment_settings": server_kg_enrichment_settings.model_dump_json(),
                        "user": auth_user.json(),
                    }

                    return await self.orchestration_provider.run_workflow(  # type: ignore
                        "enrich-graph", {"request": workflow_input}, {}
                    )
                else:
                    from core.main.orchestration import simple_kg_factory

                    logger.info("Running enrich-graph without orchestration.")
                    simple_kg = simple_kg_factory(self.service)
                    await simple_kg["enrich-graph"](workflow_input)
                    return {
                        "message": "Graph communities created successfully.",
                        "task_id": None,
                    }

        @self.router.get("/entities")
        @self.base_endpoint
        async def get_entities(
            collection_id: Optional[UUID] = Query(
                None, description="Collection ID to retrieve entities from."
            ),
            entity_level: Optional[DataLevel] = Query(
                default=DataLevel.DOCUMENT,
                description="Type of entities to retrieve. Options are: raw, dedup_document, dedup_collection.",
            ),
            entity_ids: Optional[list[str]] = Query(
                None, description="Entity IDs to filter by."
            ),
            offset: int = Query(0, ge=0, description="Offset for pagination."),
            limit: int = Query(
                100,
                ge=-1,
                description="Number of items to return. Use -1 to return all items.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedEntitiesResponse:  # type: ignore
            """
            Retrieve entities from the knowledge graph.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            if entity_level == DataLevel.CHUNK:
                entity_table_name = "chunk_entity"
            elif entity_level == DataLevel.DOCUMENT:
                entity_table_name = "entity"
            else:
                entity_table_name = "collection_entity"

            get_entities_response = await self.service.get_entities(
                collection_id=collection_id,
                entity_ids=entity_ids,
                entity_table_name=entity_table_name,
                offset=offset,
                limit=limit,
            )

            return get_entities_response["entities"], {  # type: ignore
                "total_entries": get_entities_response["total_entries"]
            }

        @self.router.get("/triples")
        @self.base_endpoint
        async def get_relationships(
            collection_id: Optional[UUID] = Query(
                None,
                description="Collection ID to retrieve relationships from.",
            ),
            entity_names: Optional[list[str]] = Query(
                None, description="Entity names to filter by."
            ),
            triple_ids: Optional[list[str]] = Query(
                None, description="Relationship IDs to filter by."
            ),
            offset: int = Query(0, ge=0, description="Offset for pagination."),
            limit: int = Query(
                100,
                ge=-1,
                description="Number of items to return. Use -1 to return all items.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedRelationshipsResponse:
            """
            Retrieve relationships from the knowledge graph.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            get_relationships_response = await self.service.get_relationships(
                offset=offset,
                limit=limit,
                collection_id=collection_id,
                entity_names=entity_names,
                relationship_ids=triple_ids,
            )

            return get_relationships_response["relationships"], {  # type: ignore
                "total_entries": get_relationships_response["total_entries"]
            }

        @self.router.get("/communities")
        @self.base_endpoint
        async def get_communities(
            collection_id: Optional[UUID] = Query(
                None, description="Collection ID to retrieve communities from."
            ),
            levels: Optional[list[int]] = Query(
                None, description="Levels to filter by."
            ),
            community_ids: Optional[list[int]] = Query(
                None, description="Community numbers to filter by."
            ),
            offset: int = Query(0, ge=0, description="Offset for pagination."),
            limit: int = Query(
                100,
                ge=-1,
                description="Number of items to return. Use -1 to return all items.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ) -> WrappedCommunitiesResponse:
            """
            Retrieve communities from the knowledge graph.
            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            get_communities_response = await self.service.get_communities(
                offset=offset,
                limit=limit,
                collection_id=collection_id,
                levels=levels,
                community_ids=community_ids,
            )

            return get_communities_response["communities"], {  # type: ignore
                "total_entries": get_communities_response["total_entries"]
            }

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
        ):
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
                self.service.providers.database.config.kg_entity_deduplication_settings
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
                description="The name of the prompt to tune. Valid options are 'graphrag_relationships_extraction_few_shot', 'graphrag_entity_description' and 'graphrag_communities'.",
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
            collection_id: UUID = Body(  # FIXME: This should be a path parameter
                ..., description="Collection ID to delete graph for."
            ),
            cascade: bool = Body(  # FIXME: This should be a query parameter
                default=False,
                description="Whether to cascade the deletion, and delete entities and relationships belonging to the collection.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            """
            Delete the graph for a given collection. Note that this endpoint may delete a large amount of data created by the KG pipeline, this deletion is irreversible, and recreating the graph may be an expensive operation.

            Notes:
            The endpoint deletes all communities for a given collection. If the cascade flag is set to true, the endpoint also deletes all the entities and relationships associated with the collection.

            WARNING: Setting this flag to true will delete entities and relationships for documents that are shared across multiple collections. Do not set this flag unless you are absolutely sure that you want to delete the entities and relationships for all documents in the collection.

            """
            if not auth_user.is_superuser:
                logger.warning("Implement permission checks here.")

            await self.service.delete_graph_for_collection(
                collection_id, cascade
            )

            return {"message": "Graph deleted successfully."}
