import logging

from fastapi import APIRouter, Depends, HTTPException

from ...abstractions import (
    R2RAnalyticsRequest,
    R2RDeleteRequest,
    R2RDocumentChunksRequest,
    R2RDocumentsOverviewRequest,
    R2RLogsRequest,
    R2RUpdatePromptRequest,
    R2RUsersOverviewRequest,
)
from ...dependencies import get_r2r_app

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/update_prompt")
async def update_prompt_app(
    request: R2RUpdatePromptRequest, r2r=Depends(get_r2r_app)
):
    try:
        results = await r2r.update_prompt(
            request.name, request.template, request.input_types
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"update_prompt_app(request={request}) - \n\n{str(e)})")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/logs")
async def get_logs_app(
    request: R2RLogsRequest,
    r2r=Depends(get_r2r_app),
):
    try:
        results = await r2r.alogs(
            log_type_filter=request.log_type_filter,
            max_runs_requested=request.max_runs_requested,
        )
        return {"results": results}
    except Exception as e:
        logger.error(
            f"get_logs_app(log_type_filter={request.log_type_filter}, max_runs_requested={request.max_runs_requested}) - \n\n{str(e)})"
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/analytics")
async def get_analytics_app(
    request: R2RAnalyticsRequest, r2r=Depends(get_r2r_app)
):
    try:
        results = await r2r.aanalytics(
            filter_criteria=request.filter_criteria,
            analysis_types=request.analysis_types,
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"get_analytics_app(request={request}) - \n\n{str(e)})")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/users_overview")
async def get_users_overview_app(
    request: R2RUsersOverviewRequest, r2r=Depends(get_r2r_app)
):
    try:
        results = await r2r.ausers_overview(user_ids=request.user_ids)
        return {"results": results}
    except Exception as e:
        logger.error(
            f"get_users_overview_app(request={request}) - \n\n{str(e)})"
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/delete")
async def delete_app(request: R2RDeleteRequest, r2r=Depends(get_r2r_app)):
    try:
        results = await r2r.delete(request)
        return {"results": results}
    except Exception as e:
        logger.error(f"delete_app(request={request}) - \n\n{str(e)})")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/documents_overview")
async def get_documents_overview_app(
    request: R2RDocumentsOverviewRequest,
    r2r=Depends(get_r2r_app),
):
    try:
        results = await r2r.adocuments_overview(
            document_ids=request.document_ids, user_ids=request.user_ids
        )
        return {"results": results}
    except Exception as e:
        logger.error(
            f"get_documents_overview_app(document_ids={request.document_ids}, user_ids={request.user_ids}) - \n\n{str(e)})"
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/document_chunks")
async def get_document_chunks_app(
    request: R2RDocumentChunksRequest, r2r=Depends(get_r2r_app)
):
    try:
        results = await r2r.adocument_chunks(request.document_id)
        return {"results": results}
    except Exception as e:
        logger.error(
            f"get_document_chunks_app(request={request}) - \n\n{str(e)})"
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/app_settings")
async def get_app_settings_app(r2r=Depends(get_r2r_app)):
    try:
        results = await r2r.aapp_settings()
        return {"results": results}
    except Exception as e:
        logger.error(f"get_app_settings_app() - \n\n{str(e)})")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/openapi_spec")
def get_openapi_spec_app(r2r=Depends(get_r2r_app)):
    try:
        results = r2r.openapi_spec()
        return {"results": results}
    except Exception as e:
        logger.error(f"get_openapi_spec_app() - \n\n{str(e)})")
        raise HTTPException(status_code=500, detail=str(e)) from e
