import textwrap
from datetime import datetime, timezone
from typing import Optional

import psutil
from fastapi import Depends, Query

from core.base import R2RException
from core.base.api.models import (
    GenericMessageResponse,
    WrappedGenericMessageResponse,
    WrappedLogsResponse,
    WrappedServerStatsResponse,
    WrappedSettingsResponse,
)

from ...abstractions import R2RProviders, R2RServices
from .base_router import BaseRouterV3


class SystemRouter(BaseRouterV3):
    def __init__(
        self,
        providers: R2RProviders,
        services: R2RServices,
    ):
        super().__init__(providers, services)
        self.start_time = datetime.now(timezone.utc)

    def _setup_routes(self):
        @self.router.get(
            "/health",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.system.health()
                        """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.system.health();
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r health
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/health"\\
                                 -H "Content-Type: application/json" \\
                                 -H "Authorization: Bearer YOUR_API_KEY" \\
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def health_check() -> WrappedGenericMessageResponse:
            return GenericMessageResponse(message="ok")  # type: ignore

        @self.router.get(
            "/system/settings",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.system.settings()
                        """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.system.settings();
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r system settings
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/system/settings" \\
                                 -H "Content-Type: application/json" \\
                                 -H "Authorization: Bearer YOUR_API_KEY" \\
                        """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def app_settings(
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedSettingsResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only a superuser can call the `system/settings` endpoint.",
                    403,
                )
            return await self.services.management.app_settings()

        @self.router.get(
            "/system/status",
            dependencies=[Depends(self.rate_limit_dependency)],
            openapi_extra={
                "x-codeSamples": [
                    {
                        "lang": "Python",
                        "source": textwrap.dedent(
                            """
                            from r2r import R2RClient

                            client = R2RClient("http://localhost:7272")
                            # when using auth, do client.login(...)

                            result = client.system.status()
                        """
                        ),
                    },
                    {
                        "lang": "JavaScript",
                        "source": textwrap.dedent(
                            """
                            const { r2rClient } = require("r2r-js");

                            const client = new r2rClient("http://localhost:7272");

                            function main() {
                                const response = await client.system.status();
                            }

                            main();
                            """
                        ),
                    },
                    {
                        "lang": "CLI",
                        "source": textwrap.dedent(
                            """
                            r2r system status
                            """
                        ),
                    },
                    {
                        "lang": "cURL",
                        "source": textwrap.dedent(
                            """
                            curl -X POST "https://api.example.com/v3/system/status" \\
                                 -H "Content-Type: application/json" \\
                                 -H "Authorization: Bearer YOUR_API_KEY" \\
                            """
                        ),
                    },
                ]
            },
        )
        @self.base_endpoint
        async def server_stats(
            auth_user=Depends(self.providers.auth.auth_wrapper),
        ) -> WrappedServerStatsResponse:
            if not auth_user.is_superuser:
                raise R2RException(
                    "Only an authorized user can call the `system/status` endpoint.",
                    403,
                )
            return {  # type: ignore
                "start_time": self.start_time.isoformat(),
                "uptime_seconds": (
                    datetime.now(timezone.utc) - self.start_time
                ).total_seconds(),
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
            }
