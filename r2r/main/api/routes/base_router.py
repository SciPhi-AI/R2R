import functools
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from r2r.base import R2RException, manage_run
from r2r.base.logging.base import RunType

logger = logging.getLogger(__name__)


class BaseRouter:
    def __init__(self, engine, run_type: RunType = RunType.UNSPECIFIED):
        self.engine = engine
        self.run_type = run_type
        self.router = APIRouter()

    def base_endpoint(self, func: callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with manage_run(
                self.engine.run_manager, func.__name__
            ) as run_id:
                auth_user = kwargs.get("auth_user")
                if auth_user:
                    await self.engine.run_manager.log_run_info(
                        run_type=self.run_type,
                        user=auth_user,
                    )

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
                    await self.engine.logging_connection.log(
                        run_id=run_id,
                        key="error",
                        value=str(e),
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
