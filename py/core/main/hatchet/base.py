from hatchet_sdk import Hatchet
from dotenv import load_dotenv
# from core.pipelines.ingestion_pipeline import IngestionPipeline
# from ..services.ingestion_service import IngestionService
load_dotenv()

r2r_hatchet = Hatchet(debug=True)

@r2r_hatchet.workflow(name="ingestion-workflow", on_events=["file:ingest"])
class IngestionWorkflow:
    def __init__(self, ingestion_service):
        self.service = ingestion_service

    @r2r_hatchet.step(retries=0)
    async def ingest_files(self, context):
        # Extract necessary data from context
        files = context.get('files')
        metadatas = context.get('metadatas')
        document_ids = context.get('document_ids')
        chunking_settings = context.get('chunking_settings')
        user = context.get('user')
        print('files = ', files)
        result = self.ingestion_service.ingest_files(files, metadatas, document_ids, chunking_settings, user)

        # # Run the ingestion pipeline
        # result = await self.service.ingestion_pipeline.run(
        #     input=files,
        #     metadatas=metadatas,
        #     document_ids=document_ids,
        #     chunking_settings=chunking_settings,
        #     user=user
        # )

        return result

