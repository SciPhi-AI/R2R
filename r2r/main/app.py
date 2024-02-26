import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from r2r.core import (
    EmbeddingPipeline,
    IngestionPipeline,
    LoggingDatabaseConnection,
    RAGPipeline,
)
from r2r.main.utils import configure_logging, find_project_root, process_logs

logger = logging.getLogger("r2r")

# Current directory where this script is located
CURRENT_DIR = Path(__file__).resolve().parent


def create_app(
    ingestion_pipeline: IngestionPipeline,
    embedding_pipeline: EmbeddingPipeline,
    rag_pipeline: RAGPipeline,
    upload_path: Optional[Path] = None,
    logging_provider: Optional[LoggingDatabaseConnection] = None,
):
    app = FastAPI()
    configure_logging()

    # CORS setup
    origins = [
        "*",  # TODO - Change this to the actual frontend URL
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,  # Allows specified origins
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

    upload_path = upload_path or find_project_root(CURRENT_DIR) / "uploads"

    if not upload_path.exists():
        upload_path.mkdir()

    class EmbeddingsSettingsModel(BaseModel):
        do_chunking: Optional[bool] = True
        do_upsert: Optional[bool] = True

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

    class AddEntryRequest(BaseModel):
        entry: EntryModel
        settings: SettingsModel = SettingsModel()

    class AddEntriesRequest(BaseModel):
        entries: list[EntryModel]
        settings: SettingsModel = SettingsModel()

    class RAGQueryModel(BaseModel):
        query: str
        limit: Optional[int] = 10
        filters: dict = {}
        settings: SettingsModel = SettingsModel()

    def to_camel(string: str) -> str:
        return "".join(
            word.capitalize() if i != 0 else word
            for i, word in enumerate(string.split("_"))
        )

    class LogModel(BaseModel):
        timestamp: datetime = Field(alias="timestamp")
        pipeline_run_id: str = Field(alias="pipelineRunId")
        pipeline_run_type: str = Field(alias="pipelineRunType")
        method: str = Field(alias="method")
        result: str = Field(alias="result")
        log_level: str = Field(alias="logLevel")

        class Config:
            alias_generator = to_camel
            allow_population_by_field_name = True

    class SummaryLogModel(BaseModel):
        timestamp: datetime = Field(alias="timestamp")
        pipeline_run_id: str = Field(alias="pipelineRunId")
        pipeline_run_type: str = Field(alias="pipelineRunType")
        method: str = Field(alias="method")
        search_query: str = Field(alias="searchQuery")
        search_results: list[dict] = Field(alias="searchResults")
        completion_result: str = Field(alias="completionResult")
        outcome: str = Field(alias="outcome")

        class Config:
            alias_generator = to_camel
            allow_population_by_field_name = True

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
        if file_extension not in ingestion_pipeline.supported_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types are: {', '.join(ingestion_pipeline.supported_types)}.",
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

    @app.post("/add_entry/")
    def add_entry(entry_req: AddEntryRequest):
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
                f":add_entry: [Error](entry={entry_req}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/add_entries/")
    def add_entries(entries_req: AddEntriesRequest):
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
                f":add_entries: [Error](entries={entries_req}, error={str(e)})"
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
                f":rag_completion: [Error](query={query}, error={str(e)})"
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
    def logs():
        try:
            if logging_provider is None:
                raise HTTPException(
                    status_code=404, detail="Logging provider not found."
                )
            logs = logging_provider.get_logs()
            return {
                "logs": [LogModel(**log).dict(by_alias=True) for log in logs]
            }
        except Exception as e:
            logger.error(f":logs: [Error](error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/logs_summary")
    def logs_summary():
        try:
            if logging_provider is None:
                raise HTTPException(
                    status_code=404, detail="Logging provider not found."
                )
            logs = logging_provider.get_logs()
            logs_summary = process_logs(logs)
            events_summary = [
                SummaryLogModel(**log).dict(by_alias=True)
                for log in logs_summary
            ]
            return {"events_summary": events_summary}
        except Exception as e:
            logger.error(f":logs_summary: [Error](error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    return app
