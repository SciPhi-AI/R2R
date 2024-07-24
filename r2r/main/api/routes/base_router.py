import functools
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from r2r.base import R2RException, manage_run

logger = logging.getLogger(__name__)


class BaseRouter:
    def __init__(self, engine):
        self.engine = engine
        self.router = APIRouter()

    def base_endpoint(self, func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with manage_run(
                self.engine.run_manager, func.__name__
            ) as run_id:
                try:
                    results = await func(*args, **kwargs)
                    if isinstance(results, StreamingResponse):
                        return results
                    return {"results": results}
                except R2RException as re:
                    raise HTTPException(
                        status_code=re.status_code,
                        detail={
                            "message": re.message,
                            "error_type": type(re).__name__,
                        },
                    )
                except Exception as e:
                    # Get the pipeline name based on the function name
                    pipeline_name = f"{func.__name__.split('_')[0]}_pipeline"

                    # Safely get the pipeline object and its type
                    pipeline = getattr(
                        self.engine.pipelines, pipeline_name, None
                    )
                    pipeline_type = getattr(
                        pipeline, "pipeline_type", "unknown"
                    )

                    await self.engine.logging_connection.log(
                        log_id=run_id,
                        key="pipeline_type",
                        value=pipeline_type,
                        is_info_log=True,
                    )
                    await self.engine.logging_connection.log(
                        log_id=run_id,
                        key="error",
                        value=str(e),
                        is_info_log=False,
                    )
                    logger.error(f"{func.__name__}() - \n\n{str(e)})")
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "message": f"An error '{e}' occurred during {func.__name__}",
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                    ) from e

        return wrapper

    @classmethod
    def build_router(cls, engine):
        return cls(engine).router
