import functools
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from r2r.base import manage_run

from ...engine import R2REngine
from ...services.ingestion_service import IngestionService
from ..requests import (
    R2RIngestDocumentsRequest,
    R2RIngestFilesRequest,
    R2RUpdateDocumentsRequest,
    R2RUpdateFilesRequest,
)

logger = logging.getLogger(__name__)


def create_ingestion_router(engine: R2REngine):
    router = APIRouter()

    def ingestion_endpoint(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with manage_run(engine.run_manager, func.__name__) as run_id:
                try:
                    results = await func(*args, **kwargs)
                    return {"results": results}
                except HTTPException as he:
                    raise he
                except Exception as e:
                    await engine.logging_connection.log(
                        log_id=run_id,
                        key="pipeline_type",
                        value=engine.pipelines.ingestion_pipeline.pipeline_type,
                        is_info_log=True,
                    )
                    await engine.logging_connection.log(
                        log_id=run_id,
                        key="error",
                        value=str(e),
                        is_info_log=False,
                    )
                    logger.error(f"{func.__name__}() - \n\n{str(e)})")
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "message": f"An error occurred during {func.__name__}",
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    ) from e

        return wrapper

    @router.post("/ingest_documents")
    @ingestion_endpoint
    async def ingest_documents_app(request: R2RIngestDocumentsRequest):
        return await engine.aingest_documents(
            request.documents, request.versions
        )

    @router.post("/update_documents")
    @ingestion_endpoint
    async def update_documents_app(request: R2RUpdateDocumentsRequest):
        return await engine.aupdate_documents(
            request.documents, request.versions, request.metadatas
        )

    @router.post("/ingest_files")
    @ingestion_endpoint
    async def ingest_files_app(
        files: list[UploadFile] = File(...),
        request: R2RIngestFilesRequest = Depends(
            IngestionService.parse_ingest_files_form_data
        ),
    ):
        return await engine.aingest_files(
            files=files,
            metadatas=request.metadatas,
            document_ids=request.document_ids,
            user_ids=request.user_ids,
            versions=request.versions,
            skip_document_info=request.skip_document_info,
        )

    @router.post("/update_files")
    @ingestion_endpoint
    async def update_files_app(
        files: list[UploadFile] = File(...),
        request: R2RUpdateFilesRequest = Depends(
            IngestionService.parse_update_files_form_data
        ),
    ):
        return await engine.aupdate_files(
            files=files,
            metadatas=request.metadatas,
            document_ids=request.document_ids,
        )

    return router
