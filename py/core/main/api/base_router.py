import functools
import logging
from abc import abstractmethod
from typing import Callable, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.base import R2RException, manage_run
from core.base.logging.base import RunType
from core.base.providers import OrchestrationProvider

from ..services.base import Service

logger = logging.getLogger(__name__)


class BaseRouter:
    def __init__(
        self,
        service: "Service",
        orchestration_provider: OrchestrationProvider,
        run_type: RunType = RunType.UNSPECIFIED,
    ):
        self.service = service
        self.run_type = run_type
        self.orchestration_provider = orchestration_provider
        self.router = APIRouter()
        self.openapi_extras = self._load_openapi_extras()
        self._setup_routes()
        self._register_workflows()

    def get_router(self):
        return self.router

    def base_endpoint(self, func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with manage_run(
                self.service.run_manager, func.__name__
            ) as run_id:
                auth_user = kwargs.get("auth_user")
                if auth_user:
                    await self.service.run_manager.log_run_info(
                        run_type=self.run_type,
                        user=auth_user,
                    )

                try:
                    func_result = await func(*args, **kwargs)
                    if (
                        isinstance(func_result, tuple)
                        and len(func_result) == 2
                    ):
                        results, outer_kwargs = func_result
                    else:
                        results, outer_kwargs = func_result, {}

                    if isinstance(results, StreamingResponse):
                        return results
                    return {"results": results, **outer_kwargs}

                except R2RException as re:
                    raise HTTPException(
                        status_code=re.status_code,
                        detail={
                            "message": re.message,
                            "error_type": type(re).__name__,
                        },
                    )

                except Exception as e:

                    await self.service.logging_connection.log(
                        run_id=run_id,
                        key="error",
                        value=str(e),
                    )

                    logger.error(
                        f"Error in base endpoint {func.__name__}() - \n\n{str(e)}",
                        exc_info=True,
                    )

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

    @abstractmethod
    def _setup_routes(self):
        pass

    def _register_workflows(self):
        pass

    def _load_openapi_extras(self):
        return {}
