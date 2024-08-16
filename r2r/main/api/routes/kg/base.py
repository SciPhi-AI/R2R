from fastapi import Depends

from r2r.main.api.routes.base_router import BaseRouter
from r2r.main.engine import R2REngine


class KGRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.setup_routes()

    def setup_routes(self):
        @self.router.post("/enrich_graph")
        @self.base_endpoint
        async def enrich_graph(
            request: dict,
            auth_user=(
                Depends(self.engine.providers.auth.auth_wrapper)
                if self.engine.providers.auth
                else None
            ),
        ):
            return await self.engine.enrich_graph()
