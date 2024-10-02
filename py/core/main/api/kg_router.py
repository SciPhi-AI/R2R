import logging
from pathlib import Path
from typing import Optional

import yaml
from fastapi import Body, Depends
from pydantic import Json

from core.base import KGCreationSettings, KGEnrichmentSettings, R2RException
from core.base.api.models import (
    WrappedKGCreationResponse,
    WrappedKGEnrichmentResponse,
)
from core.base.providers import OrchestrationProvider, Workflow
from core.utils import generate_default_user_collection_id

from ..services.kg_service import KgService
from .base_router import BaseRouter, RunType

logger = logging.getLogger(__name__)


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
        self.orchestration_provider.register_workflows(
            Workflow.KG,
            self.service,
            {
                "create-graph": "Graph creation task queued successfully.",
                "enrich-graph": "Graph enrichment task queued successfully.",
            },
        )

    def _setup_routes(self):
        @self.router.post(
            "/create_graph",
        )
        @self.base_endpoint
        async def create_graph(
            collection_id: str = Body(
                description="Collection ID to create graph for.",
            ),
            run_type: Optional[RunType] = Body(
                description="Run an estimate or the full graph creation process.",
            ),
            kg_creation_settings: Optional[
                Union[dict, KGCreationSettings]
            ] = Body(
                default="{}",
                description="Settings for the graph creation process.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
            response_model=WrappedKGCreationResponse,
        ):
            """
            Creating a graph on your documents. This endpoint takes input a list of document ids and KGCreationSettings. If document IDs are not provided, the graph will be created on all documents in the system.

            This step extracts the relevant entities and relationships from the documents and creates a graph based on the extracted information.

            In order to do GraphRAG, you will need to run the enrich_graph endpoint.
            """

            if not auth_user.is_superuser:
                raise R2RException(
                    status_code=403,
                    message="Authentication failed: Only superusers can create graph.",
                )

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            if isinstance(kg_creation_settings, str):
                kg_creation_settings = json.loads(kg_creation_settings)
            server_kg_creation_settings = (
                self.service.providers.kg.config.kg_creation_settings
            )
            if kg_creation_settings:
                for key, value in kg_creation_settings.items():
                    if value is not None:
                        setattr(server_kg_creation_settings, key, value)

            if run_type == "estimate":

                graph_estimate = await self.service.get_creation_estimate(
                    collection_id
                )
                return {"message": graph_estimate}

            elif run_type == "full":
                workflow_input = {
                    "collection_id": collection_id,
                    "kg_creation_settings": server_kg_creation_settings.model_dump_json(),
                    "user": auth_user.json(),
                }

                return await self.orchestration_provider.run_workflow(
                    "create-graph", {"request": workflow_input}, {}
                )

            else:
                raise R2RException(
                    status_code=400,
                    message="Invalid run type. Please specify either 'estimate' or 'full'.",
                )

        @self.router.post(
            "/enrich_graph",
        )
        @self.base_endpoint
        async def enrich_graph(
            collection_id: str = Body(
                description="Collection name to enrich graph for.",
            ),
            run_type: Optional[RunType] = Body(
                description="Run an estimate or the full graph enrichment process.",
            ),
            kg_enrichment_settings: Optional[
                Union[dict, KGEnrichmentSettings]
            ] = Body(
                default="{}",
                description="Settings for the graph enrichment process.",
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
            response_model=WrappedKGEnrichmentResponse,
        ):
            """
            This endpoint enriches the graph with additional information. It creates communities of nodes based on their similarity and adds embeddings to the graph. This step is necessary for GraphRAG to work.
            """

            if not auth_user.is_superuser:
                raise R2RException(
                    status_code=403,
                    message="Authentication failed: Only superusers can enrich graph.",
                )

            if not collection_id:
                collection_id = generate_default_user_collection_id(
                    auth_user.id
                )

            server_kg_enrichment_settings = (
                self.service.providers.kg.config.kg_enrichment_settings
            )

            if kg_enrichment_settings:
                for key, value in kg_enrichment_settings.items():
                    if value is not None:
                        setattr(server_kg_enrichment_settings, key, value)

            if run_type == "estimate":

                clustering_result = await self.service.get_enrichment_estimate(
                    collection_id
                )
                return {"message": clustering_result}

            elif run_type == "full":
                workflow_input = {
                    "collection_id": collection_id,
                    "kg_enrichment_settings": server_kg_enrichment_settings.model_dump_json(),
                    "run_type": run_type,
                    "user": auth_user.json(),
                }

                return await self.orchestration_provider.run_workflow(
                    "enrich-graph", {"request": workflow_input}, {}
                )

            else:
                raise R2RException(
                    status_code=400,
                    message="Invalid run type. Please specify either 'estimate' or 'full'.",
                )

        @self.router.post(
            "/delete_graph_for_documents",
        )
        @self.base_endpoint
        async def delete_graph_for_documents(
            document_ids: list[str] = Body(
                description="List of document IDs to delete graph for."
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):

            if not auth_user.is_superuser:
                raise R2RException(
                    status_code=403,
                    message="Authentication failed: Only superusers can delete graph for documents.",
                )

            return await self.service.delete_graph_for_documents(document_ids)

        @self.router.post(
            "/delete_graph_for_collection",
        )
        @self.base_endpoint
        async def delete_graph_for_collection(
            collection_id: str = Body(
                description="Collection ID to delete graph for."
            ),
            cascade: bool = Body(
                description="Whether to delete document level graph and all associated triples.",
                default=False,
            ),
            auth_user=Depends(self.service.providers.auth.auth_wrapper),
        ):
            if not auth_user.is_superuser:
                raise R2RException(
                    status_code=403,
                    message="Authentication failed: Only superusers can delete graph for collection.",
                )

            return await self.service.delete_graph_for_collection(
                collection_id, cascade
            )
