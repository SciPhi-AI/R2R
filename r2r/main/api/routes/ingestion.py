import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from r2r.base import manage_run

from ...services.ingestion_service import IngestionService
from ..requests import (
    R2RIngestDocumentsRequest,
    R2RIngestFilesRequest,
    R2RUpdateDocumentsRequest,
    R2RUpdateFilesRequest,
)

logger = logging.getLogger(__name__)


def setup_routes(app, engine):
    router = APIRouter()

    @router.post("/ingest_documents")
    async def ingest_documents_app(request: R2RIngestDocumentsRequest):
        async with manage_run(
            engine.run_manager, "ingest_documents_app"
        ) as run_id:
            try:
                results = await engine.aingest_documents(
                    request.documents, request.versions
                )
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
                logger.error(
                    f"ingest_documents_app(documents={request.documents}) - \n\n{str(e)})"
                )
                raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/update_documents")
    async def update_documents_app(request: R2RUpdateDocumentsRequest):
        async with manage_run(
            engine.run_manager, "update_documents_app"
        ) as run_id:
            try:
                results = await engine.aupdate_documents(
                    request.documents, request.versions, request.metadatas
                )
                return {"results": results}
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
                logger.error(
                    f"update_documents_app(documents={request.documents}) - \n\n{str(e)})"
                )
                raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/ingest_files")
    async def ingest_files_app(
        files: list[UploadFile] = File(...),
        request: R2RIngestFilesRequest = Depends(
            IngestionService.parse_ingest_files_form_data
        ),
    ):
        async with manage_run(
            engine.run_manager, "ingest_files_app"
        ) as run_id:
            try:
                results = await engine.aingest_files(
                    files=files,
                    metadatas=request.metadatas,
                    document_ids=request.document_ids,
                    user_ids=request.user_ids,
                    versions=request.versions,
                    skip_document_info=request.skip_document_info,
                )
                return {"results": results}
            except HTTPException as he:
                raise HTTPException(he.status_code, he.detail) from he
            except Exception as e:
                logger.error(f"ingest_files() - \n\n{str(e)})")
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
                raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/update_files")
    async def update_files_app(
        files: list[UploadFile] = File(...),
        request: R2RUpdateFilesRequest = Depends(
            IngestionService.parse_update_files_form_data
        ),
    ):
        async with manage_run(
            engine.run_manager, "update_files_app"
        ) as run_id:
            try:
                results = await engine.aupdate_files(
                    files=files,
                    metadatas=request.metadatas,
                    document_ids=request.document_ids,
                )
                return {"results": results}
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
                raise HTTPException(status_code=500, detail=str(e)) from e

    app.include_router(router, prefix="/v1")
