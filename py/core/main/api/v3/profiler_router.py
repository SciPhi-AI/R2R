import asyncio
import os
import logging
from fastapi import HTTPException
from pyinstrument import Profiler
from pyinstrument.renderers.speedscope import SpeedscopeRenderer
from fastapi import Depends, Query

from core.base.api.models import (
    GenericMessageResponse,
    WrappedGenericMessageResponse
)
from ...abstractions import R2RProviders, R2RServices
from ...config import R2RConfig
from .base_router import BaseRouterV3

logger = logging.getLogger(__name__)

class ProfileRouter(BaseRouterV3):
    def __init__(
        self, providers: R2RProviders, services: R2RServices, config: R2RConfig
    ):
        logger.info("Initializing ProfileRouter")
        super().__init__(providers, services, config)

    def _register_workflows(self):
        # No workflows to register for this router
        pass

    def _setup_routes(self):
        @self.router.get(
            "/profile", 
            tags=["system"],
            response_model=WrappedGenericMessageResponse,
            summary="Profile system performance",
            dependencies=[Depends(self.rate_limit_dependency)]
        )
        @self.base_endpoint
        async def profile_system(
            duration: int = Query(
                30, 
                description="Profile duration in seconds",
                ge=1,
                le=300
            )
        ):
            """
            Profile the application for the specified duration (in seconds).
            
            This endpoint runs a profiler on the application for the specified duration
            and saves the results to a speedscope-compatible JSON file.
            
            The profile can be visualized by uploading the resulting file to https://www.speedscope.app/.
            
            - **duration**: Number of seconds to run the profiler (between 1 and 300)
            """
            try:
                profile_path = os.path.join(os.getcwd(), f"profile_{duration}s.speedscope.json")
                
                profiler = Profiler()
                profiler.start()
                
                await asyncio.sleep(duration)
                
                profiler.stop()
                renderer = SpeedscopeRenderer()
                output_data = renderer.render(profiler.last_session)
                
                with open(profile_path, 'w') as f:
                    f.write(output_data)
                
                return {
                    "profile_path": profile_path,
                    "duration": duration,
                    "message": f"Profile saved to {profile_path}"
                }
            except Exception as e:
                logger.error(f"Error during profiling: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Profiling failed: {str(e)}"
                )
