import logging
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from sciphi_r2r.core import EmbeddingPipeline, IngestionPipeline, RAGPipeline
from sciphi_r2r.main.utils import configure_logging, find_project_root

logger = logging.getLogger("sciphi_r2r")

# Current directory where this script is located
CURRENT_DIR = Path(__file__).resolve().parent


def create_app(
    ingestion_pipeline: IngestionPipeline,
    embedding_pipeline: EmbeddingPipeline,
    rag_pipeline: RAGPipeline,
    upload_path: Optional[Path] = None,
):
    app = FastAPI()
    configure_logging()

    upload_path = upload_path or find_project_root(CURRENT_DIR) / "uploads"

    if not upload_path.exists():
        upload_path.mkdir()

    class EntryModel(BaseModel):
        document_id: str
        blobs: dict[str, str]
        metadata: Optional[dict]

    class EmbeddingsSettingsModel(BaseModel):
        do_chunking: Optional[bool] = True

    class IngestionSettingsModel(BaseModel):
        pass

    class RAGSettingsModel(BaseModel):
        pass

    class UpsertEntryRequest(BaseModel):
        entry: EntryModel
        embedding_settings: EmbeddingsSettingsModel = EmbeddingsSettingsModel()
        ingestion_settings: IngestionSettingsModel = IngestionSettingsModel()
        rag_settings: RAGSettingsModel = RAGSettingsModel()

    class UpsertEntriesRequest(BaseModel):
        entries: list[EntryModel]
        embedding_settings: EmbeddingsSettingsModel = EmbeddingsSettingsModel()
        ingestion_settings: IngestionSettingsModel = IngestionSettingsModel()
        rag_settings: RAGSettingsModel = RAGSettingsModel()

    class RAGQueryModel(BaseModel):
        query: str
        limit: Optional[int] = 10
        filters: dict = {}

    @app.post("/upsert_entry/")
    def upsert_entry(entry_req: UpsertEntryRequest):
        try:
            document = ingestion_pipeline.run(
                entry_req.entry.document_id,
                entry_req.entry.blobs,
                metadata=entry_req.entry.metadata,
                **entry_req.ingestion_settings.dict(),
            )
            embedding_pipeline.run(
                document, **entry_req.embedding_settings.dict()
            )
            return {"message": "Entry upserted successfully."}
        except Exception as e:
            logger.error(
                f":upsert_entry: [Error](entry={entry_req}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upsert_entries/")
    def upsert_entries(entries_req: UpsertEntriesRequest):
        try:
            for entry in entries_req.entries:
                documents = ingestion_pipeline.run(
                    entry.document_id,
                    entry.blobs,
                    metadata=entry.metadata,
                    **entries_req.ingestion_settings.dict(),
                )
                embedding_pipeline.run(
                    documents, **entries_req.embedding_settings.dict()
                )
            return {"message": "Entries upserted successfully."}
        except Exception as e:
            logger.error(
                f":upsert_entries: [Error](entries={entries_req}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/search/")
    def search(query: RAGQueryModel):
        try:
            completion = rag_pipeline.run(
                query.query, query.filters, query.limit, search_only=True
            )
            return completion
        except Exception as e:
            logger.error(f":search: [Error](query={query}, error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/rag_completion/")
    def rag_completion(query: RAGQueryModel):
        try:
            completion = rag_pipeline.run(
                query.query, query.filters, query.limit
            )
            return completion
        except Exception as e:
            logger.error(
                f":completion: [Error](query={query}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/filtered_deletion/")
    def filtered_deletion(key: str, value: Union[bool, int, str]):
        try:
            embedding_pipeline.db.filtered_deletion(key, value)
            return {"message": "Entries deleted successfully."}
        except Exception as e:
            logger.error(
                f":filtered_deletion: [Error](key={key}, value={value}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    return app
