import logging

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from r2r.base import (
    GenerationConfig,
    KGSearchSettings,
    VectorSearchSettings,
    manage_run,
)

from ...engine import R2REngine
from ..requests import R2REvalRequest, R2RRAGRequest, R2RSearchRequest

logger = logging.getLogger(__name__)


def setup_routes(app: FastAPI, engine: R2REngine):
    router = APIRouter()

    @router.post("/search")
    async def search_app(request: R2RSearchRequest):
        async with manage_run(engine.run_manager, "search_app") as run_id:
            try:
                results = await engine.asearch(
                    query=request.query,
                    vector_search_settings=request.vector_search_settings
                    or VectorSearchSettings(),
                    kg_search_settings=request.kg_search_settings
                    or KGSearchSettings(),
                )
                return {"results": results}
            except Exception as e:
                await engine.logging_connection.log(
                    log_id=run_id,
                    key="pipeline_type",
                    value=engine.pipelines.search_pipeline.pipeline_type,
                    is_info_log=True,
                )
                await engine.logging_connection.log(
                    log_id=run_id,
                    key="error",
                    value=str(e),
                    is_info_log=False,
                )
                raise HTTPException(status_code=500, detail=str(e))

    @router.post("/rag")
    async def rag_app(request: R2RRAGRequest):
        async with manage_run(engine.run_manager, "rag_app") as run_id:
            try:
                response = await engine.arag(
                    query=request.query,
                    vector_search_settings=request.vector_search_settings
                    or VectorSearchSettings(),
                    kg_search_settings=request.kg_search_settings
                    or KGSearchSettings(),
                    rag_generation_config=request.rag_generation_config
                    or GenerationConfig(model="gpt-4o"),
                )

                if (
                    request.rag_generation_config
                    and request.rag_generation_config.stream
                ):
                    return StreamingResponse(
                        response, media_type="application/json"
                    )
                else:
                    return {"results": response}
            except Exception as e:
                await engine.logging_connection.log(
                    log_id=run_id,
                    key="pipeline_type",
                    value=engine.pipelines.rag_pipeline.pipeline_type,
                    is_info_log=True,
                )
                await engine.logging_connection.log(
                    log_id=run_id,
                    key="error",
                    value=str(e),
                    is_info_log=False,
                )
                raise HTTPException(status_code=500, detail=str(e))

    @router.post("/evaluate")
    async def evaluate_app(request: R2REvalRequest):
        async with manage_run(engine.run_manager, "evaluate_app") as run_id:
            try:
                results = await engine.aevaluate(
                    query=request.query,
                    context=request.context,
                    completion=request.completion,
                )
                return {"results": results}
            except Exception as e:
                await engine.logging_connection.log(
                    log_id=run_id,
                    key="pipeline_type",
                    value=engine.pipelines.rag_pipeline.pipeline_type,
                    is_info_log=True,
                )
                await engine.logging_connection.log(
                    log_id=run_id,
                    key="error",
                    value=str(e),
                    is_info_log=False,
                )
                raise HTTPException(status_code=500, detail=str(e))

    app.include_router(router, prefix="/v1")
