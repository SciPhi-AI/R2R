import logging

from fastapi import APIRouter, HTTPException

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


def setup_routes(app, engine):
    router = APIRouter()

    @router.get("/health")
    async def health_check():
        return {"response": "ok"}

    @router.post("/update_prompt")
    async def update_prompt_app(request: R2RUpdatePromptRequest):
        try:
            results = await engine.update_prompt(
                request.name, request.template, request.input_types
            )
            return {"results": results}
        except Exception as e:
            logger.error(
                f"update_prompt_app(request={request}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/logs")
    @router.get("/logs")
    async def get_logs_app(request: R2RLogsRequest):
        try:
            results = await engine.alogs(
                log_type_filter=request.log_type_filter,
                max_runs_requested=request.max_runs_requested,
            )
            return {"results": results}
        except Exception as e:
            logger.error(
                f"get_logs_app(log_type_filter={request.log_type_filter}, max_runs_requested={request.max_runs_requested}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/analytics")
    @router.get("/analytics")
    async def get_analytics_app(request: R2RAnalyticsRequest):
        try:
            results = await engine.aanalytics(
                filter_criteria=request.filter_criteria,
                analysis_types=request.analysis_types,
            )
            return {"results": results}
        except Exception as e:
            logger.error(
                f"get_analytics_app(request={request}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/users_overview")
    @router.get("/users_overview")
    async def get_users_overview_app(request: R2RUsersOverviewRequest):
        try:
            results = await engine.ausers_overview(user_ids=request.user_ids)
            return {"results": results}
        except Exception as e:
            logger.error(
                f"get_users_overview_app(request={request}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.delete("/delete")
    async def delete_app(request: R2RDeleteRequest):
        try:
            results = await engine.adelete(
                keys=request.keys, values=request.values
            )
            return {"results": results}
        except Exception as e:
            logger.error(f"delete_app(request={request}) - \n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/documents_overview")
    @router.get("/documents_overview")
    async def get_documents_overview_app(request: R2RDocumentsOverviewRequest):
        try:
            results = await engine.adocuments_overview(
                document_ids=request.document_ids, user_ids=request.user_ids
            )
            return {"results": results}
        except Exception as e:
            logger.error(
                f"get_documents_overview_app(document_ids={request.document_ids}, user_ids={request.user_ids}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post("/document_chunks")
    @router.get("/document_chunks")
    async def get_document_chunks_app(request: R2RDocumentChunksRequest):
        try:
            results = await engine.adocument_chunks(request.document_id)
            return {"results": results}
        except Exception as e:
            logger.error(
                f"get_document_chunks_app(request={request}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.get("/app_settings")
    async def get_app_settings_app():
        try:
            results = await engine.aapp_settings()
            return {"results": results}
        except Exception as e:
            logger.error(f"get_app_settings_app() - \n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.get("/openapi_spec")
    def get_openapi_spec_app():
        try:
            results = engine.openapi_spec()
            return {"results": results}
        except Exception as e:
            logger.error(f"get_openapi_spec_app() - \n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e)) from e

    app.include_router(router, prefix="/v1")
