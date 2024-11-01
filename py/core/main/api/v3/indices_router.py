import logging
from typing import Any, Optional, Union
from uuid import UUID

import yaml
from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel, Json

from core.base import R2RException, RunType  # IndexConfig,
from core.base.abstractions import (
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
    VectorTableName,
)

# from core.base.api.models import (
#     WrappedCreateIndexResponse,
#     WrappedDeleteIndexResponse,
#     WrappedGetIndexResponse,
#     WrappedListIndicesResponse,
#     WrappedUpdateIndexResponse,
# )
from core.base.api.models import (  # WrappedUpdateResponse,
    WrappedCreateVectorIndexResponse,
    WrappedDeleteVectorIndexResponse,
    WrappedListVectorIndicesResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from .base_router import BaseRouterV3

logger = logging.getLogger()


class IndexConfig(BaseModel):
    # table_name: Optional[VectorTableName] = Body(
    #     default=VectorTableName.VECTORS,
    #     description=create_vector_descriptions.get("table_name"),
    # ),
    # index_method: IndexMethod = Body(
    #     default=IndexMethod.hnsw,
    #     description=create_vector_descriptions.get("index_method"),
    # ),
    # index_measure: IndexMeasure = Body(
    #     default=IndexMeasure.cosine_distance,
    #     description=create_vector_descriptions.get("index_measure"),
    # ),
    # index_arguments: Optional[
    #     Union[IndexArgsIVFFlat, IndexArgsHNSW]
    # ] = Body(
    #     None,
    #     description=create_vector_descriptions.get("index_arguments"),
    # ),
    # index_name: Optional[str] = Body(
    #     None,
    #     description=create_vector_descriptions.get("index_name"),
    # ),
    # index_column: Optional[str] = Body(
    #     None,
    #     description=create_vector_descriptions.get("index_column"),
    # ),
    # concurrently: bool = Body(
    #     default=True,
    #     description=create_vector_descriptions.get("concurrently"),
    # ),
    # auth_user=Depends(self.service.providers.auth.auth_wrapper),
    table_name: Optional[str] = VectorTableName.VECTORS
    index_method: Optional[str] = IndexMethod.hnsw
    index_measure: Optional[str] = IndexMeasure.cosine_distance
    index_arguments: Optional[dict] = Union[IndexArgsIVFFlat, IndexArgsHNSW]
    index_name: str = None
    index_column: Optional[str] = None
    concurrently: bool = True


class IndicesRouter(BaseRouterV3):

    def __init__(
        self,
        providers,
        services,
        orchestration_provider: Union[
            HatchetOrchestrationProvider, SimpleOrchestrationProvider
        ],
        run_type: RunType = RunType.INGESTION,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _setup_routes(self):
        @self.router.post("/indices")
        @self.base_endpoint
        async def create_index(
            config: IndexConfig = Body(...),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedCreateVectorIndexResponse:
            """
            Create a new index with the specified configuration.
            """
            # TODO: Implement index creation logic
            pass

        @self.router.get("/indices")
        @self.base_endpoint
        async def list_indices(
            offset: int = Query(0, ge=0),
            limit: int = Query(10, ge=1, le=100),
            filter_by: Optional[Json[dict]] = Query(None),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedListVectorIndicesResponse:
            """
            List available indices with pagination support.
            """
            # TODO: Implement index listing logic
            pass

        @self.router.get("/indices/{id}")
        @self.base_endpoint
        async def get_index(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):  #  -> WrappedGetIndexResponse:
            """
            Get details of a specific index.
            """
            # TODO: Implement get index logic
            pass

        @self.router.put("/indices/{id}")
        @self.base_endpoint
        async def update_index(
            id: UUID = Path(...),
            config: IndexConfig = Body(...),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):  # -> WrappedUpdateIndexResponse:
            """
            Update an existing index's configuration.
            """
            # TODO: Implement index update logic
            pass

        @self.router.delete("/indices/{id}")
        @self.base_endpoint
        async def delete_index(
            id: UUID = Path(...),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedDeleteVectorIndexResponse:
            """
            Delete an existing index.
            """
            # TODO: Implement index deletion logic
            pass
