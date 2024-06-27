import functools
import logging

from fastapi import APIRouter, HTTPException
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


def create_retrieval_router(engine: R2REngine):
    router = APIRouter()

    def retrieval_endpoint(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with manage_run(engine.run_manager, func.__name__) as run_id:
                try:
                    results = await func(*args, **kwargs)
                    return results
                except HTTPException as he:
                    raise he
                except Exception as e:
                    await engine.logging_connection.log(
                        log_id=run_id,
                        key="pipeline_type",
                        value=getattr(
                            engine.pipelines,
                            f"{func.__name__.split('_')[0]}_pipeline",
                        ).pipeline_type,
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

    @router.post("/search")
    @retrieval_endpoint
    async def search_app(request: R2RSearchRequest):
        results = await engine.asearch(
            query=request.query,
            vector_search_settings=request.vector_search_settings
            or VectorSearchSettings(),
            kg_search_settings=request.kg_search_settings
            or KGSearchSettings(),
        )
        return {"results": results}

    @router.post("/rag")
    @retrieval_endpoint
    async def rag_app(request: R2RRAGRequest):
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
            return StreamingResponse(response, media_type="application/json")
        else:
            return {"results": response[0]}

    @router.post("/evaluate")
    @retrieval_endpoint
    async def evaluate_app(request: R2REvalRequest):
        results = await engine.aevaluate(
            query=request.query,
            context=request.context,
            completion=request.completion,
        )
        return {"results": results}

    return router
