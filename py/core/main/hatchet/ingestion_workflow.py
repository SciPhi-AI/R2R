from .base import r2r_hatchet
from hatchet_sdk import Context

from ..services import IngestionService, IngestionServiceAdapter


@r2r_hatchet.workflow(name="ingestion-workflow", on_events=["file:ingest"])
class IngestionWorkflow:
    def __init__(self, ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service

    @r2r_hatchet.step(retries=0)
    async def ingest_files(self, context: Context) -> None:
        # Extract necessary data from context
        data = context.workflow_input()["request"]

        parsed_data = IngestionServiceAdapter.parse_ingest_files_input(data)
        
        await self.ingestion_service.ingest_files(**parsed_data)