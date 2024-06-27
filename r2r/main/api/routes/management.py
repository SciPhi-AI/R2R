import functools
import logging

from fastapi import APIRouter, HTTPException

from ...engine import R2REngine
from ..requests import (
    R2RAnalyticsRequest,
    R2RDeleteRequest,
    R2RDocumentChunksRequest,
    R2RDocumentsOverviewRequest,
    R2RLogsRequest,
    R2RUpdatePromptRequest,
    R2RUsersOverviewRequest,
)

logger = logging.getLogger(__name__)


def create_management_router(engine: R2REngine):
    router = APIRouter()

    def management_endpoint(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                results = await func(*args, **kwargs)
                return {"results": results}
            except HTTPException as he:
                raise he
            except Exception as e:
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

    @router.get("/health")
    async def health_check():
        return {"response": "ok"}

    @router.post("/update_prompt")
    @management_endpoint
    async def update_prompt_app(request: R2RUpdatePromptRequest):
        return await engine.aupdate_prompt(
            request.name, request.template, request.input_types
        )

    @router.post("/logs")
    @router.get("/logs")
    @management_endpoint
    async def get_logs_app(request: R2RLogsRequest):
        return await engine.alogs(
            log_type_filter=request.log_type_filter,
            max_runs_requested=request.max_runs_requested,
        )

    @router.post("/analytics")
    @router.get("/analytics")
    @management_endpoint
    async def get_analytics_app(request: R2RAnalyticsRequest):
        return await engine.aanalytics(
            filter_criteria=request.filter_criteria,
            analysis_types=request.analysis_types,
        )

    @router.post("/users_overview")
    @router.get("/users_overview")
    @management_endpoint
    async def get_users_overview_app(request: R2RUsersOverviewRequest):
        return await engine.ausers_overview(user_ids=request.user_ids)

    @router.delete("/delete")
    @management_endpoint
    async def delete_app(request: R2RDeleteRequest):
        return await engine.adelete(keys=request.keys, values=request.values)

    @router.post("/documents_overview")
    @router.get("/documents_overview")
    @management_endpoint
    async def get_documents_overview_app(request: R2RDocumentsOverviewRequest):
        return await engine.adocuments_overview(
            document_ids=request.document_ids, user_ids=request.user_ids
        )

    @router.post("/document_chunks")
    @router.get("/document_chunks")
    @management_endpoint
    async def get_document_chunks_app(request: R2RDocumentChunksRequest):
        return await engine.adocument_chunks(request.document_id)

    @router.get("/app_settings")
    @management_endpoint
    async def get_app_settings_app():
        return await engine.aapp_settings()

    @router.get("/openapi_spec")
    @management_endpoint
    def get_openapi_spec_app():
        return engine.openapi_spec()

    return router
