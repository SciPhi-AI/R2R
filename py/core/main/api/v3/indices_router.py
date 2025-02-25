import logging
import textwrap
from typing import Optional

from fastapi import Body, Depends, Path, Query

from core.base import IndexConfig, R2RException
from core.base.abstractions import VectorTableName
from core.base.api.models import (
    VectorIndexResponse,
    VectorIndicesResponse,
    WrappedGenericMessageResponse,
    WrappedVectorIndexResponse,
    WrappedVectorIndicesResponse,
)

from ...abstractions import R2RProviders, R2RServices
from ...config import R2RConfig
from .base_router import BaseRouterV3

logger = logging.getLogger()


class IndicesRouter(BaseRouterV3):
    def __init__(
        self, providers: R2RProviders, services: R2RServices, config: R2RConfig
    ):
        logging.info("Initializing IndicesRouter")
        super().__init__(providers, services, config)

    def _setup_routes(self):
        ## TODO - Allow developer to pass the index id with the request
        @self.router.post(
            "/indices",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Create Vector Index",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            # when using auth, do client.login(...)

                            # Create an HNSW index for efficient similarity search
                            result = client.indices.create(
                                config={
                                    "table_name": "chunks",  # The table containing vector embeddings
                                    "index_method": "hnsw",   # Hierarchical Navigable Small World graph
                                    "index_measure": "cosine_distance",  # Similarity measure
                                    "index_arguments": {
                                        "m": 16,              # Number of connections per layer
                                        "ef_construction": 64,# Size of dynamic candidate list for construction
                                        "ef": 40,            # Size of dynamic candidate list for search
                                    },
                                    "index_name": "my_document_embeddings_idx",
                                    "index_column": "embedding",
                                    "concurrently": True     # Build index without blocking table writes
                                },
                                run_with_orchestration=True  # Run as orchestrated task for large indices
                            )

                            # Create an IVF-Flat index for balanced performance
                            result = client.indices.create(
                                config={
                                    "table_name": "chunks",
                                    "index_method": "ivf_flat", # Inverted File with Flat storage
                                    "index_measure": "l2_distance",
                                    "index_arguments": {
                                        "lists": 100,         # Number of cluster centroids
                                        "probe": 10,          # Number of clusters to search
                                    },
                                    "index_name": "my_ivf_embeddings_idx",
                                    "index_column": "embedding",
                                    "concurrently": True
                                }
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.indicies.create({
                                    config: {
                                        tableName: "vectors",
                                        indexMethod: "hnsw",
                                        indexMeasure: "cosine_distance",
                                        indexArguments: {
                                            m: 16,
                                            ef_construction: 64,
                                            ef: 40
                                        },
                                        indexName: "my_document_embeddings_idx",
                                        indexColumn: "embedding",
                                        concurrently: true
                                    },
                                    runWithOrchestration: true
                                });
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            # Create HNSW Index
                            curl -X POST "https://api.example.com/indices" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "config": {
                                    "table_name": "vectors",
                                    "index_method": "hnsw",
                                    "index_measure": "cosine_distance",
                                    "index_arguments": {
                                    "m": 16,
                                    "ef_construction": 64,
                                    "ef": 40
                                    },
                                    "index_name": "my_document_embeddings_idx",
                                    "index_column": "embedding",
                                    "concurrently": true
                                },
                                "run_with_orchestration": true
                                }'

                            # Create IVF-Flat Index
                            curl -X POST "https://api.example.com/indices" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "config": {
                                    "table_name": "vectors",
                                    "index_method": "ivf_flat",
                                    "index_measure": "l2_distance",
                                    "index_arguments": {
                                    "lists": 100,
                                    "probe": 10
                                    },
                                    "index_name": "my_ivf_embeddings_idx",
                                    "index_column": "embedding",
                                    "concurrently": true
                                }
                                }'
                                """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_index(
            config: IndexConfig,
            run_with_orchestration: Optional[bool] = Body(
                True,
                description="Whether to run index creation as an orchestrated task (recommended for large indices)",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGenericMessageResponse:
            """Create a new vector similarity search index in over the target
            table. Allowed tables include 'vectors', 'entity',
            'document_collections'. Vectors correspond to the chunks of text
            that are indexed for similarity search, whereas entity and
            document_collections are created during knowledge graph
            construction.

            This endpoint creates a database index optimized for efficient similarity search over vector embeddings.
            It supports two main indexing methods:

            1. HNSW (Hierarchical Navigable Small World):
               - Best for: High-dimensional vectors requiring fast approximate nearest neighbor search
               - Pros: Very fast search, good recall, memory-resident for speed
               - Cons: Slower index construction, more memory usage
               - Key parameters:
                 * m: Number of connections per layer (higher = better recall but more memory)
                 * ef_construction: Build-time search width (higher = better recall but slower build)
                 * ef: Query-time search width (higher = better recall but slower search)

            2. IVF-Flat (Inverted File with Flat Storage):
               - Best for: Balance between build speed, search speed, and recall
               - Pros: Faster index construction, less memory usage
               - Cons: Slightly slower search than HNSW
               - Key parameters:
                 * lists: Number of clusters (usually sqrt(n) where n is number of vectors)
                 * probe: Number of nearest clusters to search

            Supported similarity measures:
            - cosine_distance: Best for comparing semantic similarity
            - l2_distance: Best for comparing absolute distances
            - ip_distance: Best for comparing raw dot products

            Notes:
            - Index creation can be resource-intensive for large datasets
            - Use run_with_orchestration=True for large indices to prevent timeouts
            - The 'concurrently' option allows other operations while building
            - Index names must be unique per table
            """
            # TODO: Implement index creation logic
            logger.info(
                f"Creating vector index for {config.table_name} with method {config.index_method}, measure {config.index_measure}, concurrently {config.concurrently}"
            )

            result = await self.providers.orchestration.run_workflow(
                "create-vector-index",
                {
                    "request": {
                        "table_name": config.table_name,
                        "index_method": config.index_method,
                        "index_measure": config.index_measure,
                        "index_name": config.index_name,
                        "index_column": config.index_column,
                        "index_arguments": config.index_arguments,
                        "concurrently": config.concurrently,
                    },
                },
                options={
                    "additional_metadata": {},
                },
            )

            return result  # type: ignore

        @self.router.get(
            "/indices",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="List Vector Indices",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()

                            # List all indices
                            indices = client.indices.list(
                                offset=0,
                                limit=10
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.indicies.list({
                                    offset: 0,
                                    limit: 10,
                                    filters: { table_name: "vectors" }
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/indices?offset=0&limit=10" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json"

                            # With filters
                            curl -X GET "https://api.example.com/indices?offset=0&limit=10&filters={\"table_name\":\"vectors\"}" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_indices(
            # filters: list[str] = Query([]),
            offset: int = Query(
                0,
                ge=0,
                description="Specifies the number of objects to skip. Defaults to 0.",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedVectorIndicesResponse:
            """List existing vector similarity search indices with pagination
            support.

            Returns details about each index including:
            - Name and table name
            - Indexing method and parameters
            - Size and row count
            - Creation timestamp and last updated
            - Performance statistics (if available)

            The response can be filtered using the filter_by parameter to narrow down results
            based on table name, index method, or other attributes.
            """
            # TODO: Implement index listing logic
            indices_data = (
                await self.providers.database.chunks_handler.list_indices(
                    offset=offset, limit=limit
                )
            )

            formatted_indices = VectorIndicesResponse(
                indices=[
                    VectorIndexResponse(index=index_data)
                    for index_data in indices_data["indices"]
                ]
            )

            return (  # type: ignore
                formatted_indices,
                {"total_entries": indices_data["total_entries"]},
            )

        @self.router.get(
            "/indices/{table_name}/{index_name}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Get Vector Index Details",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()

                            # Get detailed information about a specific index
                            index = client.indices.retrieve("index_1")
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.indicies.retrieve({
                                    indexName: "index_1",
                                    tableName: "vectors"
                                });

                                console.log(response);
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            curl -X GET "https://api.example.com/indices/vectors/index_1" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def get_index(
            table_name: VectorTableName = Path(
                ...,
                description="The table of vector embeddings to delete (e.g. `vectors`, `entity`, `document_collections`)",
            ),
            index_name: str = Path(
                ..., description="The name of the index to delete"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedVectorIndexResponse:
            """Get detailed information about a specific vector index.

            Returns comprehensive information about the index including:
            - Configuration details (method, measure, parameters)
            - Current size and row count
            - Build progress (if still under construction)
            - Performance statistics:
                * Average query time
                * Memory usage
                * Cache hit rates
                * Recent query patterns
            - Maintenance information:
                * Last vacuum
                * Fragmentation level
                * Recommended optimizations
            """
            # TODO: Implement get index logic
            indices = (
                await self.providers.database.chunks_handler.list_indices(
                    filters={
                        "index_name": index_name,
                        "table_name": table_name,
                    },
                    limit=1,
                    offset=0,
                )
            )
            if len(indices["indices"]) != 1:
                raise R2RException(
                    f"Index '{index_name}' not found", status_code=404
                )
            return {"index": indices["indices"][0]}  # type: ignore

        # TODO - Implement update index
        #         @self.router.post(
        #             "/indices/{name}",
        #             summary="Update Vector Index",
        #             openapi_extra={
        #                 "x-codeSamples": [
        #                     {
        #                         "lang": "Python",
        #                         "source": """
        # from r2r import R2RClient

        # client = R2RClient()

        # # Update HNSW index parameters
        # result = client.indices.update(
        #     "550e8400-e29b-41d4-a716-446655440000",
        #     config={
        #         "index_arguments": {
        #             "ef": 80,  # Increase search quality
        #             "m": 24    # Increase connections per layer
        #         },
        #         "concurrently": True
        #     },
        #     run_with_orchestration=True
        # )""",
        #                     },
        #                     {
        #                         "lang": "Shell",
        #                         "source": """
        # curl -X PUT "https://api.example.com/indices/550e8400-e29b-41d4-a716-446655440000" \\
        #      -H "Content-Type: application/json" \\
        #      -H "Authorization: Bearer YOUR_API_KEY" \\
        #      -d '{
        #        "config": {
        #          "index_arguments": {
        #            "ef": 80,
        #            "m": 24
        #          },
        #          "concurrently": true
        #        },
        #        "run_with_orchestration": true
        #      }'""",
        #                     },
        #                 ]
        #             },
        #         )
        #         @self.base_endpoint
        #         async def update_index(
        #             id: UUID = Path(...),
        #             config: IndexConfig = Body(...),
        #             run_with_orchestration: Optional[bool] = Body(True),
        #             auth_user=Depends(self.providers.auth.auth_wrapper()),
        #         ):  # -> WrappedUpdateIndexResponse:
        #             """
        #             Update an existing index's configuration.
        #             """
        #             # TODO: Implement index update logic
        #             pass

        @self.router.delete(
            "/indices/{table_name}/{index_name}",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="Delete Vector Index",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()

                            # Delete an index with orchestration for cleanup
                            result = client.indices.delete(
                                index_name="index_1",
                                table_name="vectors",
                                run_with_orchestration=True
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.indicies.delete({
                                    indexName: "index_1"
                                    tableName: "vectors"
                                });

                                console.log(response);
                            }

                            main();
                            """),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent("""
                            curl -X DELETE "https://api.example.com/indices/index_1" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_index(
            table_name: VectorTableName = Path(
                default=...,
                description="The table of vector embeddings to delete (e.g. `vectors`, `entity`, `document_collections`)",
            ),
            index_name: str = Path(
                ..., description="The name of the index to delete"
            ),
            # concurrently: bool = Body(
            #     default=True,
            #     description="Whether to delete the index concurrently (recommended for large indices)",
            # ),
            # run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedGenericMessageResponse:
            """Delete an existing vector similarity search index.

            This endpoint removes the specified index from the database. Important considerations:

            - Deletion is permanent and cannot be undone
            - Underlying vector data remains intact
            - Queries will fall back to sequential scan
            - Running queries during deletion may be slower
            - Use run_with_orchestration=True for large indices to prevent timeouts
            - Consider index dependencies before deletion

            The operation returns immediately but cleanup may continue in background.
            """
            logger.info(
                f"Deleting vector index {index_name} from table {table_name}"
            )

            return await self.providers.orchestration.run_workflow(  # type: ignore
                "delete-vector-index",
                {
                    "request": {
                        "index_name": index_name,
                        "table_name": table_name,
                        "concurrently": True,
                    },
                },
                options={
                    "additional_metadata": {},
                },
            )
