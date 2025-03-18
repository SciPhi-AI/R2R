import json
import logging
import textwrap
from typing import Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query

from core.base import (
    ChunkResponse,
    GraphSearchSettings,
    R2RException,
    SearchSettings,
    UpdateChunk,
    select_search_filters,
)
from core.base.api.models import (
    GenericBooleanResponse,
    WrappedBooleanResponse,
    WrappedChunkResponse,
    WrappedChunksResponse,
    WrappedVectorSearchResponse,
)

from ...abstractions import R2RProviders, R2RServices
from ...config import R2RConfig
from .base_router import BaseRouterV3

logger = logging.getLogger()

MAX_CHUNKS_PER_REQUEST = 1024 * 100


class ChunksRouter(BaseRouterV3):
    def __init__(
        self, providers: R2RProviders, services: R2RServices, config: R2RConfig
    ):
        logging.info("Initializing ChunksRouter")
        super().__init__(providers, services, config)

    def _setup_routes(self):
        @self.router.post(
            "/chunks/search",
            summary="Search Chunks",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            response = client.chunks.search(
                                query="search query",
                                search_settings={
                                    "limit": 10
                                }
                            )
                            """),
                    }
                ]
            },
        )
        @self.base_endpoint
        async def search_chunks(
            query: str = Body(...),
            search_settings: SearchSettings = Body(
                default_factory=SearchSettings,
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedVectorSearchResponse:  # type: ignore
            # TODO - Deduplicate this code by sharing the code on the retrieval router
            """Perform a semantic search query over all stored chunks.

            This endpoint allows for complex filtering of search results using PostgreSQL-based queries.
            Filters can be applied to various fields such as document_id, and internal metadata values.

            Allowed operators include `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, and `nin`.
            """

            search_settings.filters = select_search_filters(
                auth_user, search_settings
            )

            search_settings.graph_settings = GraphSearchSettings(enabled=False)

            results = await self.services.retrieval.search(
                query=query,
                search_settings=search_settings,
            )
            return results.chunk_search_results  # type: ignore

        @self.router.get(
            "/chunks/{id}",
            summary="Retrieve Chunk",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            response = client.chunks.retrieve(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.chunks.retrieve({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def retrieve_chunk(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedChunkResponse:
            """Get a specific chunk by its ID.

            Returns the chunk's content, metadata, and associated
            document/collection information. Users can only retrieve chunks
            they own or have access to through collections.
            """
            chunk = await self.services.ingestion.get_chunk(id)
            if not chunk:
                raise R2RException("Chunk not found", 404)

            # TODO - Add collection ID check
            if not auth_user.is_superuser and str(auth_user.id) != str(
                chunk["owner_id"]
            ):
                raise R2RException("Not authorized to access this chunk", 403)

            return ChunkResponse(  # type: ignore
                id=chunk["id"],
                document_id=chunk["document_id"],
                owner_id=chunk["owner_id"],
                collection_ids=chunk["collection_ids"],
                text=chunk["text"],
                metadata=chunk["metadata"],
                # vector = chunk["vector"] # TODO - Add include vector flag
            )

        @self.router.post(
            "/chunks/{id}",
            summary="Update Chunk",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            response = client.chunks.update(
                                {
                                    "id": "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    "text": "Updated content",
                                    "metadata": {"key": "new value"}
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
                                const response = await client.chunks.update({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    text: "Updated content",
                                    metadata: {key: "new value"}
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_chunk(
            id: UUID = Path(...),
            chunk_update: UpdateChunk = Body(...),
            # TODO: Run with orchestration?
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedChunkResponse:
            """Update an existing chunk's content and/or metadata.

            The chunk's vectors will be automatically recomputed based on the
            new content. Users can only update chunks they own unless they are
            superusers.
            """
            # Get the existing chunk to get its chunk_id
            existing_chunk = await self.services.ingestion.get_chunk(
                chunk_update.id
            )
            if existing_chunk is None:
                raise R2RException(f"Chunk {chunk_update.id} not found", 404)

            workflow_input = {
                "document_id": str(existing_chunk["document_id"]),
                "id": str(chunk_update.id),
                "text": chunk_update.text,
                "metadata": chunk_update.metadata
                or existing_chunk["metadata"],
                "user": auth_user.model_dump_json(),
            }

            logger.info("Running chunk ingestion without orchestration.")
            from core.main.orchestration import simple_ingestion_factory

            # TODO - CLEAN THIS UP

            simple_ingestor = simple_ingestion_factory(self.services.ingestion)
            await simple_ingestor["update-chunk"](workflow_input)

            return ChunkResponse(  # type: ignore
                id=chunk_update.id,
                document_id=existing_chunk["document_id"],
                owner_id=existing_chunk["owner_id"],
                collection_ids=existing_chunk["collection_ids"],
                text=chunk_update.text,
                metadata=chunk_update.metadata or existing_chunk["metadata"],
                # vector = existing_chunk.get('vector')
            )

        @self.router.delete(
            "/chunks/{id}",
            summary="Delete Chunk",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            response = client.chunks.delete(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.chunks.delete({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_chunk(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ) -> WrappedBooleanResponse:
            """Delete a specific chunk by ID.

            This permanently removes the chunk and its associated vector
            embeddings. The parent document remains unchanged. Users can only
            delete chunks they own unless they are superusers.
            """
            # Get the existing chunk to get its chunk_id
            existing_chunk = await self.services.ingestion.get_chunk(id)

            if existing_chunk is None:
                raise R2RException(
                    message=f"Chunk {id} not found", status_code=404
                )

            filters = {
                "$and": [
                    {"owner_id": {"$eq": str(auth_user.id)}},
                    {"chunk_id": {"$eq": str(id)}},
                ]
            }
            await (
                self.services.management.delete_documents_and_chunks_by_filter(
                    filters=filters
                )
            )
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.get(
            "/chunks",
            dependencies=[Depends(self.rate_limit_dependency)],
            summary="List Chunks",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent("""
                            from r2r import R2RClient

                            client = R2RClient()
                            response = client.chunks.list(
                                metadata_filter={"key": "value"},
                                include_vectors=False,
                                offset=0,
                                limit=10,
                            )
                            """),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent("""
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient();

                            function main() {
                                const response = await client.chunks.list({
                                    metadataFilter: {key: "value"},
                                    includeVectors: false,
                                    offset: 0,
                                    limit: 10,
                                });
                            }

                            main();
                            """),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def list_chunks(
            metadata_filter: Optional[str] = Query(
                None, description="Filter by metadata"
            ),
            include_vectors: bool = Query(
                False, description="Include vector data in response"
            ),
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
        ) -> WrappedChunksResponse:
            """List chunks with pagination support.

            Returns a paginated list of chunks that the user has access to.
            Results can be filtered and sorted based on various parameters.
            Vector embeddings are only included if specifically requested.

            Regular users can only list chunks they own or have access to
            through collections. Superusers can list all chunks in the system.
            """  # Build filters
            filters = {}

            # Add user access control filter
            if not auth_user.is_superuser:
                filters["owner_id"] = {"$eq": str(auth_user.id)}

            # Add metadata filters if provided
            if metadata_filter:
                metadata_filter = json.loads(metadata_filter)

            # Get chunks using the vector handler's list_chunks method
            results = await self.services.ingestion.list_chunks(
                filters=filters,
                include_vectors=include_vectors,
                offset=offset,
                limit=limit,
            )

            # Convert to response format
            chunks = [
                ChunkResponse(
                    id=chunk["id"],
                    document_id=chunk["document_id"],
                    owner_id=chunk["owner_id"],
                    collection_ids=chunk["collection_ids"],
                    text=chunk["text"],
                    metadata=chunk["metadata"],
                    vector=chunk.get("vector") if include_vectors else None,
                )
                for chunk in results["results"]
            ]

            return (chunks, {"total_entries": results["total_entries"]})  # type: ignore
