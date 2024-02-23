import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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

    # CORS setup
    origins = [
        "http://localhost:3000",  # Assuming your frontend runs on this port
        "http://localhost:8000",  # The port your backend runs on
        # You can add more origins as needed
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
        pipeline_run_type: str
        method: str
        result: str
        log_level: str

    class summaryLogModel(BaseModel):
        timestamp: datetime
        pipelineRunID: str
        pipelineRunType: str
        method: str
        searchQuery: str
        searchResult: str
        completionResult: str
        outcome: str

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
    # TODO: - Update name to getrawlogs and update on examples, etc
    def logs():
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

    # TODO: Add a field about what type of pipeline is it: search, rag, embedding, ingestion. (Look at logs, add a flag.)
    # TODO: PipelineRunType

    @app.get("/logs_summary")
    def logs_summary():
        try:
            if logging_database is None:
                raise HTTPException(
                    status_code=404, detail="Logging provider not found."
                )
            logs = logging_database.get_logs()
            events_summary = process_logs(logs)
            return {"events_summary": events_summary}
        except Exception as e:
            logger.error(f":get_logs_summary: [Error](error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    def process_logs(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        event_aggregation = {}
        for log in logs:
            update_aggregation_entries(log, event_aggregation)
        # Convert each aggregated log entry to summaryLogModel before returning
        return [
            summaryLogModel(**log).dict()
            for log in combine_aggregated_logs(event_aggregation)
        ]

    def process_result(result: str, method: str) -> str:
        if method == "search":
            text_matches = re.findall(r"'text': '([^']*)'", result)
            processed_result = ", ".join(text_matches)
            return processed_result
        elif method == "generate_completion":
            content_matches = re.findall(r"content='([^']*)'", result)
            processed_result = ", ".join(content_matches)
            return processed_result
        else:
            return result

    def update_aggregation_entries(
        log: Dict[str, Any], event_aggregation: Dict[str, Dict[str, Any]]
    ):
        pipeline_run_id = log["pipeline_run_id"]
        if pipeline_run_id is None:
            logger.error(f"Missing 'run_id' in log: {log}")
            return

        pipeline_run_type = log["pipeline_run_type"]
        if pipeline_run_type is None:
            logger.error(f"Missing 'run_type' in log: {log}")
            return

        if pipeline_run_id not in event_aggregation:
            event_aggregation[pipeline_run_id] = {
                "timestamp": log["timestamp"],
                "pipeline_run_id": pipeline_run_id,
                "pipeline_run_type": pipeline_run_type,
                "events": [],
            }
        event = {
            "method": log["method"],
            "result": log["result"],
            "log_level": log["log_level"],
            "outcome": "success" if log["log_level"] == "INFO" else "fail",
        }
        event_aggregation[pipeline_run_id]["events"].append(event)

    def combine_aggregated_logs(
        event_aggregation: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        logs_summary = []
        for run_id, aggregation in event_aggregation.items():
            # Assuming 'pipeline_run_type' is available in the log entries to determine the type of pipeline
            pipeline_type = (
                aggregation["pipeline_run_type"]
                if "pipeline_run_type" in aggregation
                else "unknown"
            )

            summary_entry = {
                "timestamp": aggregation["timestamp"],
                "pipelineRunID": run_id,
                "pipelineRunType": pipeline_type,
                "method": "",
                "searchQuery": "",
                "searchResult": "",
                "completionResult": "N/A",  # Default to "N/A" if not applicable
                "outcome": "success"
                if aggregation["events"][-1].get("log_level") == "INFO"
                else "fail",
            }

            for event in aggregation["events"]:
                if event["method"] == "ingress":
                    summary_entry["searchQuery"] = event.get("result", "N/A")
                elif event["method"] == "search":
                    summary_entry["searchResult"] = process_result(
                        event.get("result", "N/A"), event["method"]
                    )
                    summary_entry[
                        "method"
                    ] = "Search"  # Update method to reflect the action
                elif event["method"] == "generate_completion":
                    summary_entry["completionResult"] = process_result(
                        event.get("result", "N/A"), event["method"]
                    )
                    summary_entry[
                        "method"
                    ] = "Generate Completion"  # Update method to reflect the action
                else:
                    logger.error(
                        f"Unknown method in {pipeline_type} pipeline: {event['method']}"
                    )

            logs_summary.append(summary_entry)
        return [summaryLogModel(**log).dict() for log in logs_summary]

    return app
