import logging
from typing import List, Optional, Union
from uuid import UUID

from fastapi import Body, Depends, Path, Query
from pydantic import Json

from core.base import (
    R2RException,
    RawChunk,
    RunType,
    UnprocessedChunk,
    UpdateChunk,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from core.utils import generate_id
from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper

from .base_router import BaseRouterV3
from .chunk_responses import ChunkIngestionResponse, ChunkResponse

logger = logging.getLogger()

MAX_CHUNKS_PER_REQUEST = 1024 * 100


class ChunkRouter(BaseRouterV3):
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
        @self.router.post("/chunks")
        @self.base_endpoint
        async def create_chunks(
            raw_chunks: Json[list[UnprocessedChunk]] = Body(...),
            run_with_orchestration: Optional[bool] = Body(True),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[list[ChunkIngestionResponse]]:
            print("run_with_orchestration = ", run_with_orchestration)
            """
            Create multiple chunks and process them through the ingestion pipeline.
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
                    RawChunk(
                        text=chunk.text if hasattr(chunk, "text") else "",
                        metadata=chunk.metadata,
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

        @self.router.get("/chunks/{chunk_id}")
        @self.base_endpoint
        async def retrieve_chunk(
            chunk_id: UUID = Path(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[ChunkResponse]:
            """
            Get a specific chunk by its ID.
            """
            chunk = await self.services["ingestion"].get_chunk(chunk_id)
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

        @self.router.post("/chunks/{chunk_id}")
        @self.base_endpoint
        async def update_chunk(
            chunk_update: Json[UpdateChunk] = Body(...),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> ResultsWrapper[ChunkResponse]:
            """
            Update existing chunks with new content.
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

        @self.router.delete("/chunks/{chunk_id}")
        @self.base_endpoint
        async def delete_chunk(
            chunk_id: Json[UUID] = Path(...),
        ) -> ResultsWrapper[ChunkResponse]:
            """
            Update existing chunks with new content.
            """
            # Get the existing chunk to get its chunk_id
            existing_chunk = await self.services["ingestion"].get_chunk(
                chunk_id
            )
            if existing_chunk is None:
                raise R2RException(f"Chunk {id} not found", 404)

            await self.services["management"].delete(
                {"$eq": {"chunk_id": chunk_id}}
            )
            return None

        @self.router.get("/chunks")
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
            """
            # Build filters
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
