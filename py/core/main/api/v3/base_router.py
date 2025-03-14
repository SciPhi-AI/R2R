import functools
import logging
from abc import abstractmethod
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from core.base import R2RException

from ...abstractions import R2RProviders, R2RServices
from ...config import R2RConfig

logger = logging.getLogger()


class BaseRouterV3:
    def __init__(
        self, providers: R2RProviders, services: R2RServices, config: R2RConfig
    ):
        """
        :param providers: Typically includes auth, database, etc.
        :param services: Additional service references (ingestion, etc).
        """
        self.providers = providers
        self.services = services
        self.config = config
        self.router = APIRouter()
        self.openapi_extras = self._load_openapi_extras()

        # Add the rate-limiting dependency
        self.set_rate_limiting()

        # Initialize any routes
        self._setup_routes()
        self._register_workflows()

    def get_router(self):
        return self.router

    def base_endpoint(self, func: Callable):
        """
        A decorator to wrap endpoints in a standard pattern:
         - error handling
         - response shaping
        """

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                func_result = await func(*args, **kwargs)
                if isinstance(func_result, tuple) and len(func_result) == 2:
                    results, outer_kwargs = func_result
                else:
                    results, outer_kwargs = func_result, {}

                if isinstance(results, (StreamingResponse, FileResponse)):
                    return results
                return {"results": results, **outer_kwargs}

            except R2RException:
                raise
            except Exception as e:
                logger.error(
                    f"Error in base endpoint {func.__name__}() - {str(e)}",
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

        wrapper._is_base_endpoint = True  # type: ignore
        return wrapper

    @classmethod
    def build_router(cls, engine):
        """Class method for building a router instance (if you have a standard
        pattern)."""
        return cls(engine).router

    def _register_workflows(self):
        pass

    def _load_openapi_extras(self):
        return {}

    @abstractmethod
    def _setup_routes(self):
        """Subclasses override this to define actual endpoints."""
        pass

    def set_rate_limiting(self):
        """Adds a yield-based dependency for rate limiting each request.

        Checks the limits, then logs the request if the check passes.
        """

        async def rate_limit_dependency(
            request: Request,
            auth_user=Depends(self.providers.auth.auth_wrapper()),
        ):
            """1) Fetch the user from the DB (including .limits_overrides).

            2) Pass it to limits_handler.check_limits. 3) After the endpoint
            completes, call limits_handler.log_request.
            """
            # If the user is superuser, skip checks
            if auth_user.is_superuser:
                yield
                return

            user_id = auth_user.id
            route = request.scope["path"]

            # 1) Fetch the user from DB
            user = await self.providers.database.users_handler.get_user_by_id(
                user_id
            )
            if not user:
                raise HTTPException(status_code=404, detail="User not found.")

            # 2) Rate-limit check
            try:
                await self.providers.database.limits_handler.check_limits(
                    user=user,
                    route=route,  # Pass the User object
                )
            except ValueError as e:
                # If check_limits raises ValueError -> 429 Too Many Requests
                raise HTTPException(status_code=429, detail=str(e)) from e

            request.state.user_id = user_id
            request.state.route = route

            # 3) Execute the route
            try:
                yield
            finally:
                # 4) Log only POST and DELETE requests
                if request.method in ["POST", "DELETE"]:
                    await self.providers.database.limits_handler.log_request(
                        user_id, route
                    )

        # Attach the dependencies so you can use them in your endpoints
        self.rate_limit_dependency = rate_limit_dependency
