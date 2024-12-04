# TODO - Move indices to 'id' basis
# TODO - Implement update index
# TODO - Implement index data model

import logging
import textwrap
from typing import Optional

from fastapi import Body, Depends, Path, Query

from core.base import IndexConfig, R2RException, RunType
from core.base.abstractions import VectorTableName
from core.base.api.models import (
    GenericMessageResponse,
    WrappedGenericMessageResponse,
    WrappedListVectorIndicesResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from .base_router import BaseRouterV3

logger = logging.getLogger()


class IndicesRouter(BaseRouterV3):

    def __init__(
        self,
        providers,
        services,
        orchestration_provider: (
            HatchetOrchestrationProvider | SimpleOrchestrationProvider
        ),
        run_type: RunType = RunType.INGESTION,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)

    def _setup_routes(self):

        ## TODO - Allow developer to pass the index id with the request
        @self.router.post(
            "/indices",
            summary="Create Vector Index",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            # Create an HNSW index for efficient similarity search
                            result = client.indices.create(
                                config={
                                    "table_name": "vectors",  # The table containing vector embeddings
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
                                    "table_name": "vectors",
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
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

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
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
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
                                """
                        ),
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGenericMessageResponse:
            """
            Create a new vector similarity search index in over the target table. Allowed tables include 'vectors', 'entity', 'document_collections'.
            Vectors correspond to the chunks of text that are indexed for similarity search, whereas entity and document_collections are created during knowledge graph construction.

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

            raw_message = await self.orchestration_provider.run_workflow(
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

            return GenericMessageResponse(message=raw_message)  # type: ignore

        @self.router.get(
            "/indices",
            summary="List Vector Indices",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")

                            # List all indices
                            indices = client.indices.list(
                                offset=0,
                                limit=10,
                                filters={"table_name": "vectors"}
                            )

                            # Print index details
                            for idx in indices:
                                print(f"Index: {idx['name']}")
                                print(f"Method: {idx['method']}")
                                print(f"Size: {idx['size_bytes'] / 1024 / 1024:.2f} MB")
                                print(f"Row count: {idx['row_count']}")
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.indicies.list({
                                    offset: 0,
                                    limit: 10,
                                    filters: { table_name: "vectors" }
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r indices list
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/indices?offset=0&limit=10" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json"

                            # With filters
                            curl -X GET "https://api.example.com/indices?offset=0&limit=10&filters={\"table_name\":\"vectors\"}" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -H "Content-Type: application/json"
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_indices(
            filters: list[str] = Query([]),
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedListVectorIndicesResponse:
            """
            List existing vector similarity search indices with pagination support.

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
            indices = await self.providers.database.list_indices(
                offset=offset, limit=limit, filters=filters
            )
            return {"indices": indices["indices"]}, indices["page_info"]  # type: ignore

        @self.router.get(
            "/indices/{table_name}/{index_name}",
            summary="Get Vector Index Details",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")

                            # Get detailed information about a specific index
                            index = client.indices.retrieve("index_1")

                            # Access index details
                            print(f"Index Method: {index['method']}")
                            print(f"Parameters: {index['parameters']}")
                            print(f"Performance Stats: {index['stats']}")
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.indicies.retrieve({
                                    indexName: "index_1",
                                    tableName: "vectors"
                                });

                                console.log(response);
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r indices retrieve index_1 vectors
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X GET "https://api.example.com/indices/vectors/index_1" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> dict:  #  -> WrappedGetIndexResponse:
            """
            Get detailed information about a specific vector index.

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
            indices = await self.providers.database.list_indices(
                filters={"index_name": index_name, "table_name": table_name}
            )
            if len(indices["indices"]) != 1:
                raise R2RException(
                    f"Index '{index_name}' not found", status_code=404
                )
            return {"index": indices["indices"][0]}

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

        # client = R2RClient("http://localhost:7272")

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
        #             auth_user=Depends(self.providers.auth.auth_wrapper),
        #         ):  # -> WrappedUpdateIndexResponse:
        #             """
        #             Update an existing index's configuration.
        #             """
        #             # TODO: Implement index update logic
        #             pass

        @self.router.delete(
            "/indices/{table_name}/{index_name}",
            summary="Delete Vector Index",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")

                            # Delete an index with orchestration for cleanup
                            result = client.indices.delete(
                                index_name="index_1",
                                table_name="vectors",
                                run_with_orchestration=True
                            )
                            """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.indicies.delete({
                                    indexName: "index_1"
                                    tableName: "vectors"
                                });

                                console.log(response);
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r indices delete index_1 vectors
                            """
                        ),
                    },
                    {
                        "lang": "Shell",
                        "source": textwrap.dedent(
                            """
                            curl -X DELETE "https://api.example.com/indices/index_1" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY"
                            """
                        ),
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedGenericMessageResponse:
            """
            Delete an existing vector similarity search index.

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

            raw_message = await self.orchestration_provider.run_workflow(
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

            return GenericMessageResponse(message=raw_message)  # type: ignore
