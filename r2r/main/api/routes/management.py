from ...engine import R2REngine
from ..requests import (
    R2RAnalyticsRequest,
    R2RDeleteRequest,
    R2RDocumentChunksRequest,
    R2RDocumentsOverviewRequest,
    R2RLogsRequest,
    R2RUpdatePromptRequest,
    R2RUsersOverviewRequest,
)
from .base_router import BaseRouter


class ManagementRouter(BaseRouter):
    def __init__(self, engine: R2REngine):
        super().__init__(engine)
        self.setup_routes()

    def setup_routes(self):
        @self.router.get("/health")
        async def health_check():
            return {"response": "ok"}

        @self.router.post("/update_prompt")
        @self.base_endpoint
        async def update_prompt_app(request: R2RUpdatePromptRequest):
            return await self.engine.aupdate_prompt(
                request.name, request.template, request.input_types
            )

        @self.router.post("/logs")
        @self.router.get("/logs")
        @self.base_endpoint
        async def get_logs_app(request: R2RLogsRequest):
            return await self.engine.alogs(
                log_type_filter=request.log_type_filter,
                max_runs_requested=request.max_runs_requested,
            )

        @self.router.post("/analytics")
        @self.router.get("/analytics")
        @self.base_endpoint
        async def get_analytics_app(request: R2RAnalyticsRequest):
            return await self.engine.aanalytics(
                filter_criteria=request.filter_criteria,
                analysis_types=request.analysis_types,
            )

        @self.router.post("/users_overview")
        @self.router.get("/users_overview")
        @self.base_endpoint
        async def get_users_overview_app(request: R2RUsersOverviewRequest):
            return await self.engine.ausers_overview(user_ids=request.user_ids)

        @self.router.delete("/delete")
        @self.base_endpoint
        async def delete_app(request: R2RDeleteRequest):
            return await self.engine.adelete(
                keys=request.keys, values=request.values
            )

        @self.router.post("/documents_overview")
        @self.router.get("/documents_overview")
        @self.base_endpoint
        async def get_documents_overview_app(
            request: R2RDocumentsOverviewRequest,
        ):
            return await self.engine.adocuments_overview(
                document_ids=request.document_ids, user_ids=request.user_ids
            )

        @self.router.post("/document_chunks")
        @self.router.get("/document_chunks")
        @self.base_endpoint
        async def get_document_chunks_app(request: R2RDocumentChunksRequest):
            return await self.engine.adocument_chunks(request.document_id)

        @self.router.get("/app_settings")
        @self.base_endpoint
        async def get_app_settings_app():
            return await self.engine.aapp_settings()

        @self.router.get("/openapi_spec")
        @self.base_endpoint
        def get_openapi_spec_app():
            return self.engine.openapi_spec()


def create_management_router(engine: R2REngine):
    return ManagementRouter(engine).router
