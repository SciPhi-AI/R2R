from fastapi import Depends, File, UploadFile

from ...engine import R2REngine
from ...services.ingestion_service import IngestionService
from ..requests import (
    R2RIngestDocumentsRequest,
    R2RIngestFilesRequest,
    R2RUpdateDocumentsRequest,
    R2RUpdateFilesRequest,
)
from .base_router import BaseRouter


class IngestionRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.setup_routes()

    def setup_routes(self):
        @self.router.post("/ingest_documents")
        @self.base_endpoint
        async def ingest_documents_app(request: R2RIngestDocumentsRequest):
            return await self.engine.aingest_documents(
                request.documents, request.versions
            )

        @self.router.post("/update_documents")
        @self.base_endpoint
        async def update_documents_app(request: R2RUpdateDocumentsRequest):
            return await self.engine.aupdate_documents(
                request.documents, request.versions, request.metadatas
            )

        @self.router.post("/ingest_files")
        @self.base_endpoint
        async def ingest_files_app(
            files: list[UploadFile] = File(...),
            request: R2RIngestFilesRequest = Depends(
                IngestionService.parse_ingest_files_form_data
            ),
        ):
            return await self.engine.aingest_files(
                files=files,
                metadatas=request.metadatas,
                document_ids=request.document_ids,
                user_ids=request.user_ids,
                versions=request.versions,
            )

        @self.router.post("/update_files")
        @self.base_endpoint
        async def update_files_app(
            files: list[UploadFile] = File(...),
            request: R2RUpdateFilesRequest = Depends(
                IngestionService.parse_update_files_form_data
            ),
        ):
            return await self.engine.aupdate_files(
                files=files,
                metadatas=request.metadatas,
                document_ids=request.document_ids,
            )


def create_ingestion_router(engine: R2REngine):
    return IngestionRouter(engine).router
