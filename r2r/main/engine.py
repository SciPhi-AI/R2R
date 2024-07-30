from typing import Optional

from r2r.base import KVLoggingSingleton, RunManager
from r2r.base.abstractions.base import AsyncSyncMeta, syncable

from .abstractions import R2RAssistants, R2RPipelines, R2RProviders
from .assembly.config import R2RConfig
from .services.auth_service import AuthService
from .services.ingestion_service import IngestionService
from .services.management_service import ManagementService
from .services.retrieval_service import RetrievalService


class R2REngine(metaclass=AsyncSyncMeta):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        assistants: R2RAssistants,
        run_manager: Optional[RunManager] = None,
    ):
        logging_connection = KVLoggingSingleton()
        run_manager = run_manager or RunManager(logging_connection)

        self.config = config
        self.providers = providers
        self.pipelines = pipelines
        self.assistants = assistants
        self.logging_connection = KVLoggingSingleton()
        self.run_manager = run_manager

        self.ingestion_service = IngestionService(
            config,
            providers,
            pipelines,
            assistants,
            run_manager,
            logging_connection,
        )
        self.retrieval_service = RetrievalService(
            config,
            providers,
            pipelines,
            assistants,
            run_manager,
            logging_connection,
        )
        self.management_service = ManagementService(
            config,
            providers,
            pipelines,
            assistants,
            run_manager,
            logging_connection,
        )

        self.auth_service = AuthService(
            config,
            providers,
            pipelines,
            assistants,
            run_manager,
            logging_connection,
        )

    @syncable
    async def aingest_documents(self, *args, **kwargs):
        return await self.ingestion_service.ingest_documents(*args, **kwargs)

    @syncable
    async def aupdate_documents(self, *args, **kwargs):
        return await self.ingestion_service.update_documents(*args, **kwargs)

    @syncable
    async def aingest_files(self, *args, **kwargs):
        return await self.ingestion_service.ingest_files(*args, **kwargs)

    @syncable
    async def aupdate_files(self, *args, **kwargs):
        return await self.ingestion_service.update_files(*args, **kwargs)

    @syncable
    async def asearch(self, *args, **kwargs):
        return await self.retrieval_service.search(*args, **kwargs)

    @syncable
    async def arag(self, *args, **kwargs):
        return await self.retrieval_service.rag(*args, **kwargs)

    @syncable
    async def arag_agent(self, *args, **kwargs):
        return await self.retrieval_service.rag_agent(*args, **kwargs)

    @syncable
    async def aevaluate(self, *args, **kwargs):
        return await self.retrieval_service.evaluate(*args, **kwargs)

    @syncable
    async def aupdate_prompt(self, *args, **kwargs):
        return await self.management_service.update_prompt(*args, **kwargs)

    @syncable
    async def alogs(self, *args, **kwargs):
        return await self.management_service.alogs(*args, **kwargs)

    @syncable
    async def aanalytics(self, *args, **kwargs):
        return await self.management_service.aanalytics(*args, **kwargs)

    @syncable
    async def aapp_settings(self, *args, **kwargs):
        return await self.management_service.aapp_settings(*args, **kwargs)

    @syncable
    async def ausers_overview(self, *args, **kwargs):
        return await self.management_service.ausers_overview(*args, **kwargs)

    @syncable
    async def adelete(self, *args, **kwargs):
        return await self.management_service.delete(*args, **kwargs)

    @syncable
    async def adocuments_overview(self, *args, **kwargs):
        return await self.management_service.adocuments_overview(
            *args, **kwargs
        )

    @syncable
    async def ainspect_knowledge_graph(self, *args, **kwargs):
        return await self.management_service.inspect_knowledge_graph(
            *args, **kwargs
        )

    @syncable
    async def adocument_chunks(self, *args, **kwargs):
        return await self.management_service.document_chunks(*args, **kwargs)

    @syncable
    async def aregister(self, *args, **kwargs):
        return await self.auth_service.register(*args, **kwargs)

    @syncable
    async def averify_email(self, *args, **kwargs):
        return await self.auth_service.verify_email(*args, **kwargs)

    @syncable
    async def alogin(self, *args, **kwargs):
        return await self.auth_service.login(*args, **kwargs)

    @syncable
    async def auser(self, *args, **kwargs):
        return await self.auth_service.user(*args, **kwargs)

    @syncable
    async def aupdate_user(self, *args, **kwargs):
        return await self.auth_service.update_user(*args, **kwargs)

    @syncable
    async def arefresh_access_token(self, *args, **kwargs):
        return await self.auth_service.refresh_access_token(*args, **kwargs)

    @syncable
    async def achange_password(self, *args, **kwargs):
        return await self.auth_service.change_password(*args, **kwargs)

    @syncable
    async def arequest_password_reset(self, *args, **kwargs):
        return await self.auth_service.request_password_reset(*args, **kwargs)

    @syncable
    async def aconfirm_password_reset(self, *args, **kwargs):
        return await self.auth_service.confirm_password_reset(*args, **kwargs)

    @syncable
    async def alogout(self, *args, **kwargs):
        return await self.auth_service.logout(*args, **kwargs)

    @syncable
    async def adelete_user(self, *args, **kwargs):
        return await self.auth_service.delete_user(*args, **kwargs)

    @syncable
    async def aclean_expired_blacklisted_tokens(self, *args, **kwargs):
        return await self.auth_service.clean_expired_blacklisted_tokens(
            *args, **kwargs
        )
