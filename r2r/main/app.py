import json
import logging
from pathlib import Path
from typing import Generator, Optional, Union

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import StreamingResponse

from r2r.core import (
    EmbeddingPipeline,
    EvalPipeline,
    IngestionPipeline,
    LoggingDatabaseConnection,
    RAGPipeline,
)
from r2r.main.utils import (
    apply_cors,
    configure_logging,
    find_project_root,
    process_logs,
)

from .models import (
    AddEntriesRequest,
    AddEntryRequest,
    LogModel,
    RAGQueryModel,
    SettingsModel,
    SummaryLogModel,
)

logger = logging.getLogger("r2r")

# Current directory where this script is located
CURRENT_DIR = Path(__file__).resolve().parent


def create_app(
    ingestion_pipeline: IngestionPipeline,
    embedding_pipeline: EmbeddingPipeline,
    eval_pipeline: EvalPipeline,
    rag_pipeline: RAGPipeline,
    upload_path: Optional[Path] = None,
    logging_provider: Optional[LoggingDatabaseConnection] = None,
):
    app = FastAPI()
    configure_logging()
    apply_cors(app)

    upload_path = upload_path or find_project_root(CURRENT_DIR) / "uploads"

    if not upload_path.exists():
        upload_path.mkdir()

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

            # TODO - Mark upload as failed if ingestion or embedding fail partway through

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
    async def add_entry(entry_req: AddEntryRequest):
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
    async def add_entries(entries_req: AddEntriesRequest):
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
    async def search(query: RAGQueryModel):
        try:
            rag_completion = rag_pipeline.run(
                query.query, query.filters, query.limit, search_only=True
            )
            return rag_completion.search_results
        except Exception as e:
            logger.error(f":search: [Error](query={query}, error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/rag_completion/")
    async def rag_completion(
        background_tasks: BackgroundTasks, query: RAGQueryModel
    ):
        try:
            stream = query.generation_config.stream
            if not stream:
                rag_completion = rag_pipeline.run(
                    query.query,
                    query.filters,
                    query.limit,
                    generation_config=query.generation_config,
                )

                completion_text = rag_completion.completion.choices[
                    0
                ].message.content
                rag_run_id = rag_pipeline.pipeline_run_info["run_id"]
                background_tasks.add_task(
                    eval_pipeline.run,
                    query.query,
                    rag_completion.context,
                    completion_text,
                    rag_run_id,
                    **query.settings.rag_settings.dict(),
                )
                return rag_completion

            else:
                return StreamingResponse(
                    _stream_rag_completion(query, rag_pipeline),
                    media_type="text/plain",
                )
        except Exception as e:
            logger.error(
                f":rag_completion: [Error](query={query}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    async def _stream_rag_completion(
        query: RAGQueryModel,
        rag_pipeline: RAGPipeline,
    ) -> Generator[str, None, None]:
        for item in rag_pipeline.run(
            query.query,
            query.filters,
            query.limit,
            generation_config=query.generation_config,
        ):
            yield item

    @app.delete("/filtered_deletion/")
    async def filtered_deletion(key: str, value: Union[bool, int, str]):
        try:
            embedding_pipeline.db.filtered_deletion(key, value)
            return {"message": "Entries deleted successfully."}
        except Exception as e:
            logger.error(
                f":filtered_deletion: [Error](key={key}, value={value}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/logs")
    async def logs():
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
    async def logs_summary():
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
