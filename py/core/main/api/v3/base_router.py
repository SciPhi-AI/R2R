import functools
import logging
from abc import abstractmethod
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from core.base import R2RException, manage_run

from ...abstractions import R2RProviders, R2RServices

logger = logging.getLogger()


class BaseRouterV3:
    def __init__(self, providers: R2RProviders, services: R2RServices):
        self.providers = providers
        self.services = services
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
                self.services.ingestion.run_manager, func.__name__
            ) as run_id:
                auth_user = kwargs.get("auth_user")
                if auth_user:
                    await self.services.ingestion.run_manager.log_run_info(  # TODO - this is a bit of a hack
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

                except R2RException:
                    raise

                except Exception as e:

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

    def _register_workflows(self):
        pass

    def _load_openapi_extras(self):
        return {}

    @abstractmethod
    def _setup_routes(self):
        pass


import functools
import logging
from abc import abstractmethod
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from core.base import R2RException, manage_run

from ...abstractions import R2RProviders, R2RServices

logger = logging.getLogger()


class BaseRouterV3:
    def __init__(self, providers: R2RProviders, services: R2RServices):
        self.providers = providers
        self.services = services
        self.router = APIRouter()
        self.openapi_extras = self._load_openapi_extras()
        self.set_rate_limiting()
        self._setup_routes()
        self._register_workflows()

    def get_router(self):
        return self.router

    def base_endpoint(self, func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with manage_run(
                self.services.ingestion.run_manager, func.__name__
            ) as run_id:
                auth_user = kwargs.get("auth_user")
                if auth_user:
                    await self.services.ingestion.run_manager.log_run_info(
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

                except R2RException:
                    raise

                except Exception as e:
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

    def _register_workflows(self):
        pass

    def _load_openapi_extras(self):
        return {}

    @abstractmethod
    def _setup_routes(self):
        pass

    def set_rate_limiting(self):
        """
        Set up a yield dependency for rate limiting and logging.
        """

        async def rate_limit_dependency(
            request: Request,
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ):
            user_id = auth_user.id
            route = request.scope["path"]
            # Check the limits before proceeding
            try:
                await self.providers.database.limits_handler.check_limits(
                    user_id, route
                )
            except ValueError as e:
                raise HTTPException(status_code=429, detail=str(e))

            request.state.user_id = user_id
            request.state.route = route
            # Yield to run the route
            try:
                yield
            finally:
                # After the route completes successfully, log the request
                await self.providers.database.limits_handler.log_request(
                    user_id, route
                )

        self.rate_limit_dependency = rate_limit_dependency
