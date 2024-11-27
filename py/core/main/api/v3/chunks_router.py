import json
import logging
import textwrap
from copy import copy
from typing import Any, Optional
from uuid import UUID

from fastapi import Body, Depends, Path, Query

from core.base import (
    ChunkResponse,
    ChunkSearchSettings,
    GraphSearchSettings,
    R2RException,
    RunType,
    SearchSettings,
    UnprocessedChunk,
    UpdateChunk,
)
from core.base.api.models import (
    GenericBooleanResponse,
    WrappedBooleanResponse,
    WrappedChunkResponse,
    WrappedChunksResponse,
    WrappedVectorSearchResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from core.utils import generate_id

from .base_router import BaseRouterV3

logger = logging.getLogger()

MAX_CHUNKS_PER_REQUEST = 1024 * 100


class ChunksRouter(BaseRouterV3):
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

    def _select_filters(
        self,
        auth_user: Any,
        search_settings: SearchSettings,
    ) -> dict[str, Any]:

        filters = copy(search_settings.filters)
        selected_collections = None
        if not auth_user.is_superuser:
            user_collections = set(auth_user.collection_ids)
            for key in filters.keys():
                if "collection_ids" in key:
                    selected_collections = set(filters[key]["$overlap"])
                    break

            if selected_collections:
                allowed_collections = user_collections.intersection(
                    selected_collections
                )
            else:
                allowed_collections = user_collections
            # for non-superusers, we filter by user_id and selected & allowed collections
            collection_filters = {
                "$or": [
                    {"user_id": {"$eq": auth_user.id}},
                    {
                        "collection_ids": {
                            "$overlap": list(allowed_collections)
                        }
                    },
                ]  # type: ignore
            }

            filters.pop("collection_ids", None)

            filters = {"$and": [collection_filters, filters]}  # type: ignore

        return filters

    def _setup_routes(self):
        @self.router.post(
            "/chunks",
            summary="Create Chunks",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.chunks.create(
                                chunks=[
                                    {
                                        "id": "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                        "document_id": "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                        "collection_ids": ["b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"],
                                        "metadata": {"key": "value"},
                                        "text": "Some text content"
                                    }
                                ],
                                run_with_orchestration=False
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
                                const response = await client.chunks.create({
                                    chunks: [
                                        {
                                            id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                            documentId: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                            collectionIds: ["b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"],
                                            metadata: {key: "value"},
                                            text: "Some text content"
                                        }
                                    ],
                                    run_with_orchestration: false
                                });
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/chunks" \\
                                -H "Content-Type: application/json" \\
                                -H "Authorization: Bearer YOUR_API_KEY" \\
                                -d '{
                                "chunks": [{
                                    "id": "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    "document_id": "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    "collection_ids": ["b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"],
                                    "metadata": {"key": "value"},
                                    "text": "Some text content"
                                }],
                                "run_with_orchestration": false
                                }'
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_chunks(
            # TODO: We should allow ingestion directly into a collection
            raw_chunks: list[UnprocessedChunk] = Body(
                ..., description="List of chunks to create"
            ),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> Any:
            """
            Create multiple chunks and process them through the ingestion pipeline.

            This endpoint allows creating multiple chunks at once, optionally associating them
            with documents and collections. The chunks will be processed asynchronously if
            run_with_orchestration is True.

            Maximum of 100,000 chunks can be created in a single request.

            Note, it is not yet possible to add chunks to an existing document using this endpoint.
            """
            default_document_id = generate_id()
            if len(raw_chunks) > MAX_CHUNKS_PER_REQUEST:
                raise R2RException(
                    f"Maximum of {MAX_CHUNKS_PER_REQUEST} chunks per request",
                    400,
                )
            if len(raw_chunks) == 0:
                raise R2RException("No chunks provided", 400)

            # Group chunks by document_id for efficiency
            chunks_by_document: dict = {}
            for chunk in raw_chunks:
                if chunk.document_id not in chunks_by_document:
                    chunks_by_document[chunk.document_id] = []
                chunks_by_document[chunk.document_id].append(chunk)

            responses = []
            # FIXME: Need to verify that the collection_id workflow is valid
            for document_id, doc_chunks in chunks_by_document.items():
                document_id = document_id or default_document_id
                # Convert UnprocessedChunks to RawChunks for ingestion
                # FIXME: Metadata doesn't seem to be getting passed through
                raw_chunks_for_doc = [
                    UnprocessedChunk(
                        text=chunk.text if hasattr(chunk, "text") else "",
                        metadata=chunk.metadata,
                        id=chunk.id,
                    )
                    for chunk in doc_chunks
                ]

                # Prepare workflow input
                workflow_input = {
                    "document_id": str(document_id),
                    "chunks": [
                        chunk.model_dump() for chunk in raw_chunks_for_doc
                    ],
                    "metadata": {},  # Base metadata for the document
                    "user": auth_user.model_dump_json(),
                }

                # TODO - Modify create_chunks so that we can add chunks to existing document

                if run_with_orchestration:
                    # Run ingestion with orchestration
                    raw_message = (
                        await self.orchestration_provider.run_workflow(
                            "ingest-chunks",
                            {"request": workflow_input},
                            options={
                                "additional_metadata": {
                                    "document_id": str(document_id),
                                }
                            },
                        )
                    )
                    raw_message["document_id"] = str(document_id)
                    responses.append(raw_message)

                else:
                    logger.info(
                        "Running chunk ingestion without orchestration."
                    )
                    from core.main.orchestration import (
                        simple_ingestion_factory,
                    )

                    simple_ingestor = simple_ingestion_factory(
                        self.services["ingestion"]
                    )
                    await simple_ingestor["ingest-chunks"](workflow_input)

                    raw_message = {
                        "message": "Document created and ingested successfully.",
                        "document_id": str(document_id),
                        "task_id": None,
                    }
                    responses.append(raw_message)

            return responses  # type: ignore

        @self.router.post(
            "/chunks/search",
            summary="Search Chunks",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            results = client.chunks.search(
                                query="search query",
                                search_settings={
                                    "limit": 10,
                                    "min_score": 0.7
                                }
                            )
                            """
                        ),
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedVectorSearchResponse:  # type: ignore
            # TODO - Deduplicate this code by sharing the code on the retrieval router
            """
            Perform a semantic search query over all stored chunks.

            This endpoint allows for complex filtering of search results using PostgreSQL-based queries.
            Filters can be applied to various fields such as document_id, and internal metadata values.

            Allowed operators include `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `in`, and `nin`.
            """

            search_settings.filters = self._select_filters(
                auth_user, search_settings
            )

            search_settings.graph_settings = GraphSearchSettings(enabled=False)

            results = await self.services["retrieval"].search(
                query=query,
                search_settings=search_settings,
            )
            return results["chunk_search_results"]

        @self.router.get(
            "/chunks/{id}",
            summary="Retrieve Chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            chunk = client.chunks.retrieve(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
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
                                const response = await client.chunks.retrieve({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                                });
                            }

                            main();
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def retrieve_chunk(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedChunkResponse:
            """
            Get a specific chunk by its ID.

            Returns the chunk's content, metadata, and associated document/collection information.
            Users can only retrieve chunks they own or have access to through collections.
            """
            chunk = await self.services["ingestion"].get_chunk(id)
            if not chunk:
                raise R2RException("Chunk not found", 404)

            # # Check access rights
            # document = await self.services["management"].get_document(chunk.document_id)
            # TODO - Add collection ID check
            if not auth_user.is_superuser and str(auth_user.id) != str(
                chunk["user_id"]
            ):
                raise R2RException("Not authorized to access this chunk", 403)

            return ChunkResponse(  # type: ignore
                id=chunk["chunk_id"],
                document_id=chunk["document_id"],
                user_id=chunk["user_id"],
                collection_ids=chunk["collection_ids"],
                text=chunk["text"],
                metadata=chunk["metadata"],
                # vector = chunk["vector"] # TODO - Add include vector flag
            )

        @self.router.post(
            "/chunks/{id}",
            summary="Update Chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            result = client.chunks.update(
                                {
                                    "id": first_chunk_id,
                                    "text": "Updated content",
                                    "metadata": {"key": "new value"}
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
                                const response = await client.chunks.update({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                                    text: "Updated content",
                                    metadata: {key: "new value"}
                                });
                            }

                            main();
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def update_chunk(
            id: UUID = Path(...),
            chunk_update: UpdateChunk = Body(...),
            # TODO: Run with orchestration?
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedChunkResponse:
            """
            Update an existing chunk's content and/or metadata.

            The chunk's vectors will be automatically recomputed based on the new content.
            Users can only update chunks they own unless they are superusers.
            """
            # Get the existing chunk to get its chunk_id
            existing_chunk = await self.services["ingestion"].get_chunk(
                chunk_update.id
            )
            if existing_chunk is None:
                raise R2RException(f"Chunk {chunk_update.id} not found", 404)

            workflow_input = {
                "document_id": str(existing_chunk["document_id"]),
                "chunk_id": str(chunk_update.id),
                "text": chunk_update.text,
                "metadata": chunk_update.metadata
                or existing_chunk["metadata"],
                "user": auth_user.model_dump_json(),
            }

            logger.info("Running chunk ingestion without orchestration.")
            from core.main.orchestration import simple_ingestion_factory

            # TODO - CLEAN THIS UP

            simple_ingestor = simple_ingestion_factory(
                self.services["ingestion"]
            )
            await simple_ingestor["update-chunk"](workflow_input)

            return ChunkResponse(  # type: ignore
                id=chunk_update.id,
                document_id=existing_chunk["document_id"],
                user_id=existing_chunk["user_id"],
                collection_ids=existing_chunk["collection_ids"],
                text=chunk_update.text,
                metadata=chunk_update.metadata or existing_chunk["metadata"],
                # vector = existing_chunk.get('vector')
            )

        #         @self.router.post(
        #             "/chunks/{id}/enrich",
        #             summary="Enrich Chunk",
        #             openapi_extra={
        #                 "x-codeSamples": [
        #                     {
        #                         "lang": "Python",
        #                         "source": """
        # from r2r import R2RClient

        # client = R2RClient("http://localhost:7272")
        # result = client.chunks.enrich(
        #     id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
        #     enrichment_config={"key": "value"}
        # )
        # """,
        #                     }
        #                 ]
        #             },
        #         )
        #         @self.base_endpoint
        #         async def enrich_chunk(
        #             id: UUID = Path(...),
        #             enrichment_config: dict = Body(...),
        #             auth_user=Depends(self.providers.auth.auth_wrapper),
        #         ) -> ResultsWrapper[ChunkResponse]:
        #             """
        #             Enrich a chunk with additional processing and metadata.

        #             This endpoint allows adding additional enrichments to an existing chunk,
        #             such as entity extraction, classification, or custom processing defined
        #             in the enrichment_config.

        #             Users can only enrich chunks they own unless they are superusers.
        #             """
        #             pass

        @self.router.delete(
            "/chunks/{id}",
            summary="Delete Chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            result = client.chunks.delete(
                                id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
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
                                const response = await client.chunks.delete({
                                    id: "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
                                });
                            }

                            main();
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def delete_chunk(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedBooleanResponse:
            """
            Delete a specific chunk by ID.

            This permanently removes the chunk and its associated vector embeddings.
            The parent document remains unchanged. Users can only delete chunks they
            own unless they are superusers.
            """
            # Get the existing chunk to get its chunk_id
            existing_chunk = await self.services["ingestion"].get_chunk(id)
            if existing_chunk is None:
                raise R2RException(
                    message=f"Chunk {id} not found", status_code=404
                )

            filters = {
                "$and": [
                    {"user_id": {"$eq": str(auth_user.id)}},
                    {"chunk_id": {"$eq": id}},
                ]
            }
            await self.services["management"].delete(filters=filters)
            return GenericBooleanResponse(success=True)  # type: ignore

        @self.router.get(
            "/chunks",
            summary="List Chunks",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            results = client.chunks.list(
                                metadata_filter={"key": "value"},
                                include_vectors=False
                                offset=0,
                                limit=10,
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
                                const response = await client.chunks.list({
                                    metadataFilter: {key: "value"},
                                    includeVectors: false,
                                    offset: 0,
                                    limit: 10,
                                });
                            }

                            main();
                            """
                        ),
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
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedChunksResponse:
            """
            List chunks with pagination support.

            Returns a paginated list of chunks that the user has access to.
            Results can be filtered and sorted based on various parameters.
            Vector embeddings are only included if specifically requested.

            Regular users can only list chunks they own or have access to through
            collections. Superusers can list all chunks in the system.
            """  # Build filters
            filters = {}

            # Add user access control filter
            if not auth_user.is_superuser:
                filters["user_id"] = {"$eq": str(auth_user.id)}

            # Add metadata filters if provided
            if metadata_filter:
                metadata_filter = json.loads(metadata_filter)

            # Get chunks using the vector handler's list_chunks method
            results = await self.services["ingestion"].list_chunks(
                filters=filters,
                include_vectors=include_vectors,
                offset=offset,
                limit=limit,
            )

            # Convert to response format
            chunks = [
                ChunkResponse(
                    id=chunk["chunk_id"],
                    document_id=chunk["document_id"],
                    user_id=chunk["user_id"],
                    collection_ids=chunk["collection_ids"],
                    text=chunk["text"],
                    metadata=chunk["metadata"],
                    vector=chunk.get("vector") if include_vectors else None,
                )
                for chunk in results["results"]
            ]

            return (chunks, results["page_info"])  # type: ignore
