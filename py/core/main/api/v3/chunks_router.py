import logging
from typing import Any, Optional, Union
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from pydantic import BaseModel, Json

from core.base import (
    KGSearchSettings,
    R2RException,
    RawChunk,
    RunType,
    UnprocessedChunk,
    UpdateChunk,
    VectorSearchSettings,
)
from core.base.api.models import WrappedVectorSearchResponse
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from core.utils import generate_id
from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper

from .base_router import BaseRouterV3


class ChunkResponse(BaseModel):
    """Response model representing a chunk with its metadata and content."""

    document_id: UUID
    id: UUID
    collection_ids: list[UUID]
    text: str
    metadata: dict[str, Any]
    vector: Optional[list[float]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                "id": "b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
                "collection_ids": ["d09dedb1-b2ab-48a5-b950-6e1f464d83e7"],
                "text": "Sample chunk content",
                "metadata": {"key": "value"},
                "vector": [0.1, 0.2, 0.3],
            }
        }


class ChunkIngestionResponse(BaseModel):
    """Response model for chunk ingestion"""

    message: str
    document_id: UUID
    task_id: Optional[UUID] = None

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Ingestion task completed successfully",
                "document_id": "9fbe403b-c11c-5aae-8ade-ef22980c3ad1",
                "task_id": "c68dc72e-fc23-5452-8f49-d7bd46088a96",
            }
        }


logger = logging.getLogger()

MAX_CHUNKS_PER_REQUEST = 1024 * 100


class ChunksRouter(BaseRouterV3):
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

    def _select_filters(
        self,
        auth_user: Any,
        search_settings: Union[VectorSearchSettings, KGSearchSettings],
    ) -> dict[str, Any]:
        selected_collections = {
            str(cid) for cid in set(search_settings.selected_collection_ids)
        }

        if auth_user.is_superuser:
            if selected_collections:
                # For superusers, we only filter by selected collections
                filters = {
                    "collection_ids": {"$overlap": list(selected_collections)}
                }
            else:
                filters = {}
        else:
            user_collections = set(auth_user.collection_ids)

            if selected_collections:
                allowed_collections = user_collections.intersection(
                    selected_collections
                )
            else:
                allowed_collections = user_collections
            # for non-superusers, we filter by user_id and selected & allowed collections
            filters = {
                "$or": [
                    {"user_id": {"$eq": auth_user.id}},
                    {
                        "collection_ids": {
                            "$overlap": list(allowed_collections)
                        }
                    },
                ]  # type: ignore
            }

        if search_settings.filters != {}:
            filters = {"$and": [filters, search_settings.filters]}  # type: ignore

        return filters

    def _setup_routes(self):
        @self.router.post(
            "/chunks",
            summary="Create Chunks",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
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
""",
                    },
                    {
                        "lang": "cURL",
                        "source": """
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
""",
                    },
                ]
            },
        )
        @self.base_endpoint
        async def create_chunks(
            raw_chunks: Json[list[UnprocessedChunk]] = Body(
                ..., description="List of chunks to create"
            ),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[list[ChunkIngestionResponse]]:
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
            chunks_by_document = {}
            for chunk in raw_chunks:
                if chunk.document_id not in chunks_by_document:
                    chunks_by_document[chunk.document_id] = []
                chunks_by_document[chunk.document_id].append(chunk)

            responses = []
            for document_id, doc_chunks in chunks_by_document.items():
                document_id = document_id or default_document_id
                # Convert UnprocessedChunks to RawChunks for ingestion
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
                        "message": "Ingestion task completed successfully.",
                        "document_id": str(document_id),
                        "task_id": None,
                    }
                    responses.append(raw_message)

            return responses

        @self.router.post(
            "/chunks/search",
            summary="Search Chunks",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
results = client.chunks.search(
    query="search query",
    vector_search_settings={
        "limit": 10,
        "min_score": 0.7
    }
)
""",
                    }
                ]
            },
        )
        @self.base_endpoint
        async def search_chunks(
            query: str = Body(...),
            vector_search_settings: VectorSearchSettings = Body(
                default_factory=VectorSearchSettings,
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

            vector_search_settings.filters = self._select_filters(
                auth_user, vector_search_settings
            )

            kg_search_settings = KGSearchSettings(use_kg_search=False)

            results = await self.services["retrieval"].search(
                query=query,
                vector_search_settings=vector_search_settings,
                kg_search_settings=kg_search_settings,
            )
            return results["vector_search_results"]

        @self.router.get(
            "/chunks/{id}",
            summary="Retrieve Chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
chunk = client.chunks.retrieve(
    id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
)
""",
                    }
                ]
            },
        )
        @self.base_endpoint
        async def retrieve_chunk(
            id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[ChunkResponse]:
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
                chunk.user_id
            ):
                raise R2RException("Not authorized to access this chunk", 403)

            return ChunkResponse(
                id=chunk["chunk_id"],
                text=chunk["text"],
                metadata=chunk["metadata"],
                collection_ids=chunk["collection_ids"],
                document_id=chunk["document_id"],
                # vector = chunk["vector"] # TODO - Add include vector flag
            )

        @self.router.post(
            "/chunks/{id}",
            summary="Update Chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
result = client.chunks.update(
    {
        "id": first_chunk_id,
        "text": "Updated content",
        "metadata": {"key": "new value"}
    }
)
""",
                    }
                ]
            },
        )
        @self.base_endpoint
        async def update_chunk(
            id: UUID = Path(...),
            chunk_update: Json[UpdateChunk] = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[ChunkResponse]:
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
            return ChunkResponse(
                id=chunk_update.id,
                text=chunk_update.text,
                metadata=chunk_update.metadata or existing_chunk["metadata"],
                collection_ids=existing_chunk["collection_ids"],
                document_id=existing_chunk["document_id"],
                # vector = existing_chunk.get('vector')
            )

        @self.router.post(
            "/chunks/{id}/enrich",
            summary="Enrich Chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
result = client.chunks.enrich(
    id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa",
    enrichment_config={"key": "value"}
)
""",
                    }
                ]
            },
        )
        @self.base_endpoint
        async def enrich_chunk(
            id: Json[UUID] = Path(...),
            enrichment_config: Json[dict] = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[ChunkResponse]:
            """
            Enrich a chunk with additional processing and metadata.

            This endpoint allows adding additional enrichments to an existing chunk,
            such as entity extraction, classification, or custom processing defined
            in the enrichment_config.

            Users can only enrich chunks they own unless they are superusers.
            """
            pass

        @self.router.delete(
            "/chunks/{id}",
            summary="Delete Chunk",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
result = client.chunks.delete(
    id="b4ac4dd6-5f27-596e-a55b-7cf242ca30aa"
)
""",
                    }
                ]
            },
        )
        @self.base_endpoint
        async def delete_chunk(
            id: Json[UUID] = Path(...),
        ) -> ResultsWrapper[bool]:
            """
            Delete a specific chunk by ID.

            This permanently removes the chunk and its associated vector embeddings.
            The parent document remains unchanged. Users can only delete chunks they
            own unless they are superusers.
            """
            # Get the existing chunk to get its chunk_id
            existing_chunk = await self.services["ingestion"].get_chunk(id)
            if existing_chunk is None:
                raise R2RException(f"Chunk {id} not found", 404)

            await self.services["management"].delete({"$eq": {"chunk_id": id}})
            return True

        @self.router.get(
            "/chunks",
            summary="List Chunks",
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": """
from r2r import R2RClient

client = R2RClient("http://localhost:7272")
results = client.chunks.list(
    offset=0,
    limit=10,
    sort_by="created_at",
    sort_order="DESC",
    metadata_filter={"key": "value"},
    include_vectors=False
)
""",
                    }
                ]
            },
        )
        @self.base_endpoint
        async def list_chunks(
            offset: int = Query(
                0, ge=0, description="Number of records to skip"
            ),
            limit: int = Query(
                10,
                ge=1,
                le=100,
                description="Maximum number of records to return",
            ),
            sort_by: str = Query("created_at", description="Field to sort by"),
            sort_order: str = Query(
                "DESC", regex="^(ASC|DESC)$", description="Sort order"
            ),
            metadata_filter: Optional[Json[dict]] = Query(
                None, description="Filter by metadata"
            ),
            include_vectors: bool = Query(
                False, description="Include vector data in response"
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> PaginatedResultsWrapper[list[ChunkResponse]]:
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
                for key, value in metadata_filter.items():
                    filters[f"metadata.{key}"] = value

            # Get chunks using the vector handler's list_chunks method
            results = await self.services["ingestion"].list_chunks(
                offset=offset,
                limit=limit,
                filters=filters,
                sort_by=sort_by,
                sort_order=sort_order,
                include_vectors=include_vectors,
            )

            # Convert to response format
            chunks = [
                ChunkResponse(
                    id=chunk["chunk_id"],
                    text=chunk["text"],
                    metadata=chunk["metadata"],
                    collection_ids=chunk["collection_ids"],
                    document_id=chunk["document_id"],
                    vector=chunk.get("vector") if include_vectors else None,
                )
                for chunk in results["results"]
            ]

            return (chunks, results["page_info"])
