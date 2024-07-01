from typing import Optional

from r2r.base import KVLoggingSingleton, RunManager
from r2r.base.abstractions.base import AsyncSyncMeta, syncable

from .abstractions import R2RPipelines, R2RProviders
from .assembly.config import R2RConfig
from .services.ingestion_service import IngestionService
from .services.management_service import ManagementService
from .services.retrieval_service import RetrievalService


class R2REngine(metaclass=AsyncSyncMeta):
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        pipelines: R2RPipelines,
        run_manager: Optional[RunManager] = None,
    ):
        logging_connection = KVLoggingSingleton()
        run_manager = run_manager or RunManager(logging_connection)

        self.config = config
        self.providers = providers
        self.pipelines = pipelines
        self.logging_connection = KVLoggingSingleton()
        self.run_manager = run_manager

        self.ingestion_service = IngestionService(
            config, providers, pipelines, run_manager, logging_connection
        )
        self.retrieval_service = RetrievalService(
            config, providers, pipelines, run_manager, logging_connection
        )
        self.management_service = ManagementService(
            config, providers, pipelines, run_manager, logging_connection
        )

    # Ingestion routes
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

    # Retrieval routes
    @syncable
    async def asearch(self, *args, **kwargs):
        return await self.retrieval_service.search(*args, **kwargs)

    @syncable
    async def arag(self, *args, **kwargs):
        return await self.retrieval_service.rag(*args, **kwargs)

    @syncable
    async def aevaluate(self, *args, **kwargs):
        return await self.retrieval_service.evaluate(*args, **kwargs)

    # Management routes
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
    async def adocument_chunks(self, *args, **kwargs):
        return await self.management_service.document_chunks(*args, **kwargs)
