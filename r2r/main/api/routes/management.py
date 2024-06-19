import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from ...abstractions import (
    R2RAnalyticsRequest,
    R2RDeleteRequest,
    R2RDocumentChunksRequest,
    R2RUpdatePromptRequest,
    R2RUsersStatsRequest,
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
    log_type_filter: Optional[str] = None,
    max_runs_requested: int = 100,
    r2r=Depends(get_r2r_app),
):
    try:
        results = await r2r.alogs(
            log_type_filter=log_type_filter,
            max_runs_requested=max_runs_requested,
        )
        return {"results": results}
    except Exception as e:
        logger.error(
            f"get_logs_app(log_type_filter={log_type_filter}, max_runs_requested={max_runs_requested}) - \n\n{str(e)})"
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/analytics")
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


@router.get("/app_settings")
async def get_app_settings_app(r2r=Depends(get_r2r_app)):
    try:
        results = await r2r.aapp_settings()
        return {"results": results}
    except Exception as e:
        logger.error(f"get_app_settings_app() - \n\n{str(e)})")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/users_stats")
async def get_users_stats_app(
    request: R2RUsersStatsRequest, r2r=Depends(get_r2r_app)
):
    try:
        results = await r2r.ausers_stats(user_ids=request.user_ids)
        return {"results": results}
    except Exception as e:
        logger.error(f"get_users_stats_app(request={request}) - \n\n{str(e)})")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/delete")
async def delete_app(request: R2RDeleteRequest, r2r=Depends(get_r2r_app)):
    try:
        results = await r2r.delete(request)
        return {"results": results}
    except Exception as e:
        logger.error(f"delete_app(request={request}) - \n\n{str(e)})")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/documents_info")
async def get_documents_info_app(
    document_ids: Optional[List[uuid.UUID]] = None,
    user_ids: Optional[List[uuid.UUID]] = None,
    r2r=Depends(get_r2r_app),
):
    try:
        results = await r2r.adocuments_info(
            document_ids=document_ids, user_ids=user_ids
        )
        return {"results": results}
    except Exception as e:
        logger.error(
            f"get_documents_info_app(document_ids={document_ids}, user_ids={user_ids}) - \n\n{str(e)})"
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/document_chunks")
async def get_document_chunks_app(
    request: R2RDocumentChunksRequest, r2r=Depends(get_r2r_app)
):
    try:
        results = await r2r.document_chunks(request)
        return {"results": results}
    except Exception as e:
        logger.error(
            f"get_document_chunks_app(request={request}) - \n\n{str(e)})"
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/openapi_spec")
def get_openapi_spec_app(r2r=Depends(get_r2r_app)):
    try:
        results = r2r.openapi_spec()
        return {"results": results}
    except Exception as e:
        logger.error(f"get_openapi_spec_app() - \n\n{str(e)})")
        raise HTTPException(status_code=500, detail=str(e)) from e
