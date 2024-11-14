import psutil

from datetime import datetime, timezone
from fastapi import Depends

from typing import Optional

from fastapi import Depends, Query

from core.base import R2RException, RunType
from core.base.api.models import (
    GenericMessageResponse,
    WrappedGenericMessageResponse,
    WrappedLogResponse,
    WrappedServerStatsResponse,
)
from core.providers import (
    HatchetOrchestrationProvider,
    SimpleOrchestrationProvider,
)

from .base_router import BaseRouterV3


class SystemRouter(BaseRouterV3):
    def __init__(
        self,
        providers,
        services,
        orchestration_provider: (
            HatchetOrchestrationProvider | SimpleOrchestrationProvider
        ),
        run_type: RunType = RunType.MANAGEMENT,
    ):
        super().__init__(providers, services, orchestration_provider, run_type)
        self.start_time = datetime.now(timezone.utc)

    def _setup_routes(self):
        @self.router.get(
            "/health",
            include_in_schema=True,
        )
        @self.base_endpoint
        async def health_check() -> WrappedGenericMessageResponse:
            # Basic health check that doesn't require auth
            return GenericMessageResponse(message="ok")

        @self.router.get(
            "/system/status",
            include_in_schema=True,
        )
        @self.base_endpoint
        async def server_stats(
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedServerStatsResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only an authorized user can call the `server_stats` endpoint.",
                    403,
                )
            return {
                "start_time": self.start_time.isoformat(),
                "uptime_seconds": (
                    datetime.now(timezone.utc) - self.start_time
                ).total_seconds(),
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
            }

        @self.router.get("/system/logs")
        @self.base_endpoint
        async def logs(
            run_type_filter: Optional[str] = Query(""),
            offset: int = Query(
                0,
                ge=0,
                description="Specifies the number of objects to skip. Defaults to 0.",
            ),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description="Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.",
            ),
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedLogResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `logs` endpoint.", 403
                )

            return await self.services["management"].logs(
                run_type_filter=run_type_filter,
                offset=offset,
                limit=limit,
            )
