from hatchet_sdk import Context

from ..services import IngestionService, IngestionServiceAdapter
from .base import r2r_hatchet


@r2r_hatchet.workflow(name="ingestion-files", on_events=["file:ingest"])
class IngestFilesWorkflow:
    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    @r2r_hatchet.step(retries=3)
    async def ingest_files(self, context: Context) -> None:
        data = context.workflow_input()["request"]

        parsed_data = IngestionServiceAdapter.parse_ingest_files_input(data)

        await self.ingestion_service.ingest_files(**parsed_data)


@r2r_hatchet.workflow(name="update-files", on_events=["file:update"])
class UpdateFilesWorkflow:
    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    @r2r_hatchet.step(retries=3)
    async def update_files(self, context: Context) -> None:
        data = context.workflow_input()["request"]

        parsed_data = IngestionServiceAdapter.parse_update_files_input(data)

        await self.ingestion_service.update_files(**parsed_data)
