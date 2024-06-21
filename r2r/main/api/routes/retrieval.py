import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from r2r.core import GenerationConfig, manage_run

from ...abstractions import R2REvalRequest, R2RRAGRequest, R2RSearchRequest
from ...dependencies import get_r2r_app

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/search")
async def search_app(request: R2RSearchRequest, r2r=Depends(get_r2r_app)):
    async with manage_run(r2r.run_manager, "search_app") as run_id:
        try:
            return await r2r.asearch(
                query=request.query,
                vector_search_settings=request.vector_search_settings,
                kg_search_settings=request.kg_search_settings,
            )
        except Exception as e:
            await r2r.logging_connection.log(
                log_id=run_id,
                key="pipeline_type",
                value=r2r.pipelines.search_pipeline.pipeline_type,
                is_info_log=True,
            )
            await r2r.logging_connection.log(
                log_id=run_id,
                key="error",
                value=str(e),
                is_info_log=False,
            )
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag")
async def rag_app(request: R2RRAGRequest, r2r=Depends(get_r2r_app)):
    async with manage_run(r2r.run_manager, "rag_app") as run_id:
        try:
            response = await r2r.arag(
                query=request.query,
                vector_search_settings=request.vector_search_settings,
                kg_search_settings=request.kg_search_settings,
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
            await r2r.logging_connection.log(
                log_id=run_id,
                key="pipeline_type",
                value=r2r.pipelines.rag_pipeline.pipeline_type,
                is_info_log=True,
            )
            await r2r.logging_connection.log(
                log_id=run_id,
                key="error",
                value=str(e),
                is_info_log=False,
            )
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
async def evaluate_app(request: R2REvalRequest, r2r=Depends(get_r2r_app)):
    async with manage_run(r2r.run_manager, "evaluate_app") as run_id:

        try:
            return await r2r.aevaluate(
                query=request.query,
                context=request.context,
                completion=request.completion,
            )
        except Exception as e:
            await r2r.logging_connection.log(
                log_id=run_id,
                key="pipeline_type",
                value=r2r.pipelines.rag_pipeline.pipeline_type,
                is_info_log=True,
            )
            await r2r.logging_connection.log(
                log_id=run_id,
                key="error",
                value=str(e),
                is_info_log=False,
            )
            raise HTTPException(status_code=500, detail=str(e))
