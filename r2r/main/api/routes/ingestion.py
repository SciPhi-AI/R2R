import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from r2r.core import manage_run

from ...abstractions import (
    R2RIngestDocumentsRequest,
    R2RIngestFilesRequest,
    R2RUpdateDocumentsRequest,
    R2RUpdateFilesRequest,
)
from ...dependencies import get_r2r_app
from ...services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ingest_documents")
async def ingest_documents_app(
    request: R2RIngestDocumentsRequest, r2r=Depends(get_r2r_app)
):
    async with manage_run(r2r.run_manager, "ingest_documents_app") as run_id:
        try:
            results = await r2r.aingest_documents(
                request.documents, request.versions
            )
            return {"results": results}

        except HTTPException as he:
            raise he

        except Exception as e:
            await r2r.logging_connection.log(
                log_id=run_id,
                key="pipeline_type",
                value=r2r.pipelines.ingestion_pipeline.pipeline_type,
                is_info_log=True,
            )

            await r2r.logging_connection.log(
                log_id=run_id,
                key="error",
                value=str(e),
                is_info_log=False,
            )
            logger.error(
                f"ingest_documents_app(documents={request.documents}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/update_documents")
async def update_documents_app(
    request: R2RUpdateDocumentsRequest, r2r=Depends(get_r2r_app)
):
    async with manage_run(r2r.run_manager, "update_documents_app") as run_id:
        try:
            return await r2r.aingest_documents(
                request.documents, request.versions, request.metadatas
            )
        except Exception as e:
            await r2r.logging_connection.log(
                log_id=run_id,
                key="pipeline_type",
                value=r2r.pipelines.ingestion_pipeline.pipeline_type,
                is_info_log=True,
            )
            await r2r.logging_connection.log(
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
    r2r=Depends(get_r2r_app),
):
    async with manage_run(r2r.run_manager, "ingest_files_app") as run_id:
        try:
            results = await r2r.aingest_files(
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
            await r2r.logging_connection.log(
                log_id=run_id,
                key="pipeline_type",
                value=r2r.pipelines.ingestion_pipeline.pipeline_type,
                is_info_log=True,
            )

            await r2r.logging_connection.log(
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
    r2r=Depends(get_r2r_app),
):
    async with manage_run(r2r.run_manager, "update_files_app") as run_id:
        try:
            return await r2r.aingest_files(
                files=files,
                metadatas=request.metadatas,
                document_ids=request.document_ids,
            )
        except Exception as e:
            await r2r.logging_connection.log(
                log_id=run_id,
                key="pipeline_type",
                value=r2r.pipelines.ingestion_pipeline.pipeline_type,
                is_info_log=True,
            )

            await r2r.logging_connection.log(
                log_id=run_id,
                key="error",
                value=str(e),
                is_info_log=False,
            )
            raise HTTPException(status_code=500, detail=str(e)) from e
