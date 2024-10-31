import logging
from typing import Optional, Union, List
from uuid import UUID
from fastapi import Depends, Path, Query, Body
from pydantic import Json

from core.utils import generate_id
from core.base import R2RException, RunType, RawChunk, UnprocessedChunk, UpdateChunk
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)
from shared.api.models.base import PaginatedResultsWrapper, ResultsWrapper
from .base_router import BaseRouterV3
from .chunk_responses import ChunkResponse, ChunkIngestionResponse

logger = logging.getLogger()

MAX_CHUNKS_PER_REQUEST = 1024*100
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
            print('run_with_orchestration = ', run_with_orchestration)
            """
            Create multiple chunks and process them through the ingestion pipeline.
            """
            default_document_id = generate_id()
            if len(raw_chunks) > MAX_CHUNKS_PER_REQUEST:
                raise R2RException(
                    f"Maximum of {MAX_CHUNKS_PER_REQUEST} chunks per request", 400
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
                        text=chunk.text if hasattr(chunk, 'text') else "",
                        metadata=chunk.metadata
                    ) 
                    for chunk in doc_chunks
                ]

                # Prepare workflow input
                workflow_input = {
                    "document_id": str(document_id),
                    "chunks": [chunk.model_dump() for chunk in raw_chunks_for_doc],
                    "metadata": {},  # Base metadata for the document
                    "user": auth_user.model_dump_json(),
                }

                if run_with_orchestration:
                    # Run ingestion with orchestration
                    raw_message = await self.orchestration_provider.run_workflow(
                        "ingest-chunks",
                        {"request": workflow_input},
                        options={
                            "additional_metadata": {
                                "document_id": str(document_id),
                            }
                        },
                    )
                    raw_message["document_id"] = str(document_id)
                    responses.append(raw_message)

                else:
                    logger.info("Running chunk ingestion without orchestration.")
                    from core.main.orchestration import simple_ingestion_factory

                    simple_ingestor = simple_ingestion_factory(self.services["ingestion"])
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
            if not auth_user.is_superuser and str(auth_user.id) != str(chunk.user_id):
                raise R2RException("Not authorized to access this chunk", 403)

            return ChunkResponse(
                id = chunk["chunk_id"],
                text = chunk["text"],
                metadata = chunk["metadata"],
                collection_ids = chunk["collection_ids"],
                document_id = chunk["document_id"],
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
            existing_chunk = await self.services["ingestion"].get_chunk(chunk_update.id)
            if existing_chunk is None:
                raise R2RException(f"Chunk {chunk_update.id} not found", 404)

            workflow_input = {
                "document_id": str(existing_chunk['document_id']),
                "chunk_id": str(chunk_update.id),
                "text": chunk_update.text,
                "metadata": chunk_update.metadata or existing_chunk['metadata'],
                "user": auth_user.model_dump_json(),
            }

            logger.info("Running chunk ingestion without orchestration.")
            from core.main.orchestration import simple_ingestion_factory

            # TODO - CLEAN THIS UP

            simple_ingestor = simple_ingestion_factory(self.services["ingestion"])
            await simple_ingestor["update-chunk"](workflow_input)
            return ChunkResponse(
                id = chunk_update.id,
                text = chunk_update.text,
                metadata = chunk_update.metadata or existing_chunk['metadata'],
                collection_ids = existing_chunk['collection_ids'],
                document_id = existing_chunk['document_id'],
                # vector = existing_chunk.get('vector')
            )
        
        @self.router.delete("/chunks/{chunk_id}")
        @self.base_endpoint
        async def delete_chunk(
            chunk_id: Json[UUID] = Body(...),
        ) -> ResultsWrapper[ChunkResponse]:
            """
            Update existing chunks with new content.
            """
            # Get the existing chunk to get its chunk_id
            existing_chunk = await self.services["ingestion"].get_chunk(chunk_id)
            if existing_chunk is None:
                raise R2RException(f"Chunk {id} not found", 404)

            await self.services["management"].delete({"$eq": {"chunk_id": chunk_id}})
            return None

        # @self.router.get("/chunks")
        # @self.base_endpoint
        # async def list_chunks(
        #     document_id: Optional[UUID] = Query(None),
        #     offset: int = Query(0, ge=0),
        #     limit: int = Query(100, ge=1),
        #     metadata_filter: Optional[Json[dict]] = Query(None),
        #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # ) -> PaginatedResultsWrapper[List[ChunkResponse]]:
        #     # TODO - Add implementation


        # @self.router.put("/chunks/{chunk_id}")
        # @self.base_endpoint
        # async def update_chunk(
        #     chunk_id: UUID = Path(...),
        #     text: Optional[str] = Body(None),
        #     metadata: Optional[dict] = Body(None),
        #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # ) -> ResultsWrapper[ChunkResponse]:
        #     """
        #     Update a chunk's text or metadata.
        #     """
        #     chunk = await self.services["ingestion"].get_chunk(chunk_id)
        #     if not chunk:
        #         raise R2RException("Chunk not found", 404)

        #     # Check access rights
        #     document = await self.services["management"].get_document(chunk.document_id)
        #     if not auth_user.is_superuser and str(document.user_id) != str(auth_user.id):
        #         raise R2RException("Not authorized to modify this chunk", 403)

        #     updated_chunk = await self.services["ingestion"].update_chunk(
        #         chunk_id=chunk_id,
        #         text=text,
        #         metadata=metadata,
        #         user=auth_user
        #     )
        #     return updated_chunk

        # @self.router.delete("/chunks/{chunk_id}")
        # @self.base_endpoint
        # async def delete_chunk(
        #     chunk_id: UUID = Path(...),
        #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # ) -> ResultsWrapper[None]:
        #     """
        #     Delete a specific chunk.
        #     """
        #     chunk = await self.services["ingestion"].get_chunk(chunk_id)
        #     if not chunk:
        #         raise R2RException("Chunk not found", 404)

        #     # Check access rights
        #     document = await self.services["management"].get_document(chunk.document_id)
        #     if not auth_user.is_superuser and str(document.user_id) != str(auth_user.id):
        #         raise R2RException("Not authorized to delete this chunk", 403)

        #     await self.services["ingestion"].delete_chunk(chunk_id)
        #     return None

        # @self.router.get("/chunks")
        # @self.base_endpoint
        # async def list_chunks(
        #     document_id: Optional[UUID] = Query(None),
        #     offset: int = Query(0, ge=0),
        #     limit: int = Query(100, ge=1),
        #     metadata_filter: Optional[Json[dict]] = Query(None),
        #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # ) -> PaginatedResultsWrapper[List[ChunkResponse]]:
        #     """
        #     List chunks with optional filtering by document ID and metadata.
        #     """
        #     if document_id:
        #         # Check document access
        #         document = await self.services["management"].get_document(document_id)
        #         if not document:
        #             raise R2RException("Document not found", 404)
        #         if not auth_user.is_superuser and str(document.user_id) != str(auth_user.id):
        #             raise R2RException("Not authorized to access this document's chunks", 403)

        #     chunks = await self.services["ingestion"].list_chunks(
        #         document_id=document_id,
        #         metadata_filter=metadata_filter,
        #         offset=offset,
        #         limit=limit,
        #         user=auth_user
        #     )
        #     return chunks

        # # @self.router.post("/chunks/reprocess")
        # # @self.base_endpoint
        # # async def reprocess_chunks(
        # #     chunk_ids: List[UUID] = Body(...),
        # #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # # ) -> ResultsWrapper[None]:
        # #     """
        # #     Reprocess specified chunks to update their embeddings.
        # #     """
        # #     # Check access rights for all chunks
        # #     for chunk_id in chunk_ids:
        # #         chunk = await self.services["ingestion"].get_chunk(chunk_id)
        # #         if not chunk:
        # #             raise R2RException(f"Chunk {chunk_id} not found", 404)
                
        # #         document = await self.services["management"].get_document(chunk.document_id)
        # #         if not auth_user.is_superuser and str(document.user_id) != str(auth_user.id):
        # #             raise R2RException(f"Not authorized to reprocess chunk {chunk_id}", 403)

        # #     await self.services["ingestion"].reprocess_chunks(chunk_ids)
        # #     return None

        # @self.router.get("/chunks/search")
        # @self.base_endpoint
        # async def search_chunks(
        #     query: str = Query(...),
        #     filter_document_ids: Optional[List[UUID]] = Query(None),
        #     metadata_filter: Optional[Json[dict]] = Query(None),
        #     limit: int = Query(10, ge=1),
        #     min_score: float = Query(0.0, ge=0.0, le=1.0),
        #     auth_user=Depends(self.providers.auth.auth_wrapper),
        # ) -> ResultsWrapper[List[ChunkResponse]]:
        #     """
        #     Search chunks by semantic similarity to the query.
        #     """
        #     # If document IDs are provided, check access to all
        #     if filter_document_ids:
        #         for doc_id in filter_document_ids:
        #             document = await self.services["management"].get_document(doc_id)
        #             if not document:
        #                 raise R2RException(f"Document {doc_id} not found", 404)
        #             if not auth_user.is_superuser and str(document.user_id) != str(auth_user.id):
        #                 raise R2RException(f"Not authorized to search chunks from document {doc_id}", 403)

        #     results = await self.services["ingestion"].search_chunks(
        #         query=query,
        #         filter_document_ids=filter_document_ids,
        #         metadata_filter=metadata_filter,
        #         limit=limit,
        #         min_score=min_score,
        #         user=auth_user
        #     )
        #     return results