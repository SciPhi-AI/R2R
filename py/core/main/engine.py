from typing import TYPE_CHECKING, Optional

from core.base import RunLoggingSingleton, RunManager
from core.base.abstractions.base import AsyncSyncMeta, syncable

from .abstractions import R2RAgents, R2RPipelines, R2RProviders
from .services.auth_service import AuthService
from .services.ingestion_service import IngestionService
from .services.management_service import ManagementService
from .services.restructure_service import RestructureService
from .services.retrieval_service import RetrievalService

if TYPE_CHECKING:
    from .assembly.config import R2RConfig


class R2REngine(metaclass=AsyncSyncMeta):
    def __init__(
        self,
        config: "R2RConfig",
        providers: R2RProviders,
        pipelines: R2RPipelines,
        agents: R2RAgents,
        run_manager: Optional[RunManager] = None,
    ):
        logging_connection = RunLoggingSingleton()
        run_manager = run_manager or RunManager(logging_connection)

        self.config = config
        self.providers = providers
        self.pipelines = pipelines
        self.agents = agents
        self.logging_connection = RunLoggingSingleton()
        self.run_manager = run_manager

        self.ingestion_service = IngestionService(
            config,
            providers,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

        self.restructure_service = RestructureService(
            config,
            providers,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

        self.retrieval_service = RetrievalService(
            config,
            providers,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )
        self.management_service = ManagementService(
            config,
            providers,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

        self.auth_service = AuthService(
            config,
            providers,
            pipelines,
            agents,
            run_manager,
            logging_connection,
        )

    @syncable
    async def aingest_documents(self, *args, **kwargs):
        return await self.ingestion_service.ingest_documents(*args, **kwargs)

    @syncable
    async def aingest_files(self, *args, **kwargs):
        return await self.ingestion_service.ingest_files(*args, **kwargs)

    @syncable
    async def aupdate_files(self, *args, **kwargs):
        return await self.ingestion_service.update_files(*args, **kwargs)

    @syncable
    async def aenrich_graph(self, *args, **kwargs):
        return await self.restructure_service.enrich_graph(*args, **kwargs)

    @syncable
    async def asearch(self, *args, **kwargs):
        return await self.retrieval_service.search(*args, **kwargs)

    @syncable
    async def arag(self, *args, **kwargs):
        return await self.retrieval_service.rag(*args, **kwargs)

    @syncable
    async def arag_agent(self, *args, **kwargs):
        return await self.retrieval_service.agent(*args, **kwargs)

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
    async def ascore_completion(self, *args, **kwargs):
        return await self.management_service.ascore_completion(*args, **kwargs)

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

    @syncable
    async def acreate_group(self, *args, **kwargs):
        return await self.management_service.acreate_group(*args, **kwargs)

    @syncable
    async def aget_group(self, *args, **kwargs):
        return await self.management_service.aget_group(*args, **kwargs)

    @syncable
    async def aupdate_group(self, *args, **kwargs):
        return await self.management_service.aupdate_group(*args, **kwargs)

    @syncable
    async def adelete_group(self, *args, **kwargs):
        return await self.management_service.adelete_group(*args, **kwargs)

    @syncable
    async def alist_groups(self, *args, **kwargs):
        return await self.management_service.alist_groups(*args, **kwargs)

    @syncable
    async def aadd_user_to_group(self, *args, **kwargs):
        return await self.management_service.aadd_user_to_group(
            *args, **kwargs
        )

    @syncable
    async def aremove_user_from_group(self, *args, **kwargs):
        return await self.management_service.aremove_user_from_group(
            *args, **kwargs
        )

    @syncable
    async def aget_users_in_group(self, *args, **kwargs):
        return await self.management_service.aget_users_in_group(
            *args, **kwargs
        )

    @syncable
    async def aget_groups_for_user(self, *args, **kwargs):
        return await self.management_service.aget_groups_for_user(
            *args, **kwargs
        )

    @syncable
    async def aassign_document_to_group(self, *args, **kwargs):
        return await self.management_service.aassign_document_to_group(
            *args, **kwargs
        )

    @syncable
    async def agroups_overview(self, *args, **kwargs):
        return await self.management_service.agroups_overview(*args, **kwargs)

    @syncable
    async def adocuments_in_group(self, *args, **kwargs):
        return await self.management_service.adocuments_in_group(
            *args, **kwargs
        )

    @syncable
    async def adocument_groups(self, *args, **kwargs):
        return await self.management_service.adocument_groups(*args, **kwargs)

    @syncable
    async def aremove_document_from_group(self, *args, **kwargs):
        return await self.management_service.aremove_document_from_group(
            *args, **kwargs
        )
