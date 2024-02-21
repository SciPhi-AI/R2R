import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from r2r.core import (
    EmbeddingPipeline,
    IngestionPipeline,
    LoggingDatabaseConnection,
    RAGPipeline,
)
from r2r.main.utils import configure_logging, find_project_root

logger = logging.getLogger("r2r")

# Current directory where this script is located
CURRENT_DIR = Path(__file__).resolve().parent


def create_app(
    ingestion_pipeline: IngestionPipeline,
    embedding_pipeline: EmbeddingPipeline,
    rag_pipeline: RAGPipeline,
    upload_path: Optional[Path] = None,
    logging_database: Optional[LoggingDatabaseConnection] = None,
):
    app = FastAPI()
    configure_logging()

    upload_path = upload_path or find_project_root(CURRENT_DIR) / "uploads"

    if not upload_path.exists():
        upload_path.mkdir()

    class EmbeddingsSettingsModel(BaseModel):
        do_chunking: Optional[bool] = True

    class IngestionSettingsModel(BaseModel):
        pass

    class RAGSettingsModel(BaseModel):
        pass

    class SettingsModel(BaseModel):
        embedding_settings: EmbeddingsSettingsModel = EmbeddingsSettingsModel()
        ingestion_settings: IngestionSettingsModel = IngestionSettingsModel()
        rag_settings: RAGSettingsModel = RAGSettingsModel()

    class EntryModel(BaseModel):
        document_id: str
        blobs: dict[str, str]
        metadata: Optional[dict]

    # File upload class, to be fixed later
    # class FileUploadRequest(BaseModel):
    # document_id: str
    # metadata: Optional[dict]
    # settings: SettingsModel = SettingsModel()

    class UpsertEntryRequest(BaseModel):
        entry: EntryModel
        settings: SettingsModel = SettingsModel()

    class UpsertEntriesRequest(BaseModel):
        entries: list[EntryModel]
        settings: SettingsModel = SettingsModel()

    class RAGQueryModel(BaseModel):
        query: str
        limit: Optional[int] = 10
        filters: dict = {}
        settings: SettingsModel = SettingsModel()

    class LogModel(BaseModel):
        timestamp: datetime
        pipeline_run_id: str
        method: str
        result: str
        log_level: str
        message: str

    @app.post("/upload_and_process_file/")
    # TODO - Why can't we use a BaseModel to represent the request?
    # Naive class FileUploadRequest(BaseModel) above fails
    async def upload_and_process_file(
        document_id: str = Form(...),
        metadata: str = Form("{}"),
        settings: str = Form("{}"),
        file: UploadFile = File(...),
    ):
        metadata_json = json.loads(metadata)
        settings_model = SettingsModel.parse_raw(settings)

        if not file.filename:
            raise HTTPException(
                status_code=400, detail="No file was uploaded."
            )
        # Extract file extension and check if it's an allowed type
        file_extension = file.filename.split(".")[-1]
        supported_types = ingestion_pipeline.get_supported_types()
        if file_extension not in supported_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types are: {', '.join(supported_types)}.",
            )

        file_location = upload_path / file.filename
        try:
            file_content = file.file.read()

            # TODO - Consider saving file to disk
            # with open(file_location, "wb+") as file_object:
            # file_object.write(file_content)

            document = ingestion_pipeline.run(
                document_id,
                {file_extension: file_content},
                metadata=metadata_json,
                **settings_model.ingestion_settings.dict(),
            )
            embedding_pipeline.run(
                document, **settings_model.embedding_settings.dict()
            )

            return {
                "message": f"File '{file.filename}' processed and saved at '{file_location}'"
            }
        except Exception as e:
            logger.error(
                f"upload_and_process_file: [Error](file={file.filename}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upsert_entry/")
    def upsert_entry(entry_req: UpsertEntryRequest):
        try:
            document = ingestion_pipeline.run(
                entry_req.entry.document_id,
                entry_req.entry.blobs,
                metadata=entry_req.entry.metadata,
                **entry_req.settings.ingestion_settings.dict(),
            )
            embedding_pipeline.run(
                document, **entry_req.settings.embedding_settings.dict()
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
                    **entries_req.settings.ingestion_settings.dict(),
                )
                embedding_pipeline.run(
                    documents, **entries_req.settings.embedding_settings.dict()
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

    @app.get("/logs")
    def get_logs():
        try:
            if logging_database is None:
                raise HTTPException(
                    status_code=404, detail="Logging provider not found."
                )
            logs = logging_database.get_logs()
            return {"logs": [LogModel(**log) for log in logs]}
        except Exception as e:
            logger.error(f":get_logs: [Error](error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    return app
