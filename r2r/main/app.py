import json
import logging
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional, Union, cast

import requests
from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import StreamingResponse

from r2r.core import (
    EmbeddingPipeline,
    EvalPipeline,
    GenerationConfig,
    IngestionPipeline,
    LoggingDatabaseConnection,
    RAGPipeline,
    RAGPipelineOutput,
)
from r2r.main.utils import (  # configure_logging,
    R2RConfig,
    apply_cors,
    find_project_root,
    process_logs,
)

from .models import (
    AddEntriesRequest,
    AddEntryRequest,
    EvalPayloadModel,
    LogModel,
    RAGQueryModel,
    SettingsModel,
    SummaryLogModel,
)

# logger = logging.getLogger("r2r")
# logging.setLevel(logging.INFO)

# Current directory where this script is located
CURRENT_DIR = Path(__file__).resolve().parent
MB_CONVERSION_FACTOR = 1024 * 1024


def create_app(
    ingestion_pipeline: IngestionPipeline,
    embedding_pipeline: EmbeddingPipeline,
    eval_pipeline: EvalPipeline,
    rag_pipeline: RAGPipeline,
    config: R2RConfig,
    upload_path: Optional[Path] = None,
    logging_connection: Optional[LoggingDatabaseConnection] = None,
):
    app = FastAPI()
    # TODO - Consider impact of logging in remote environments
    # e.g. such as Google Cloud Run
    # configure_logging()
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

        if (
            file is not None
            and file.size
            > config.app.get("max_file_size_in_mb", 100) * MB_CONVERSION_FACTOR
        ):
            raise HTTPException(
                status_code=413,
                detail="File size exceeds maximum allowed size.",
            )

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

            documents = ingestion_pipeline.run(
                document_id,
                {file_extension: file_content},
                metadata=metadata_json,
                **settings_model.ingestion_settings.dict(),
            )
            for document in documents:
                embedding_pipeline.run(
                    document, **settings_model.embedding_settings.dict()
                )

            return {
                "message": f"File '{file.filename}' processed and saved at '{file_location}'"
            }
        except Exception as e:
            logging.error(
                f"upload_and_process_file: [Error](file={file.filename}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/add_entry/")
    async def add_entry(entry_req: AddEntryRequest):
        try:
            documents = ingestion_pipeline.run(
                entry_req.entry.document_id,
                entry_req.entry.blobs,
                metadata=entry_req.entry.metadata,
                **entry_req.settings.ingestion_settings.dict(),
            )
            for document in documents:
                embedding_pipeline.run(
                    document, **entry_req.settings.embedding_settings.dict()
                )
            return {"message": "Entry upserted successfully."}
        except Exception as e:
            logging.error(
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
                for document in documents:
                    embedding_pipeline.run(
                        document,
                        **entries_req.settings.embedding_settings.dict(),
                    )
            return {"message": "Entries upserted successfully."}
        except Exception as e:
            logging.error(
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
            logging.error(f":search: [Error](query={query}, error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/rag_completion/")
    async def rag_completion(
        background_tasks: BackgroundTasks,
        query: RAGQueryModel,
        request: Request,
    ):
        try:
            stream = query.generation_config.stream
            if not stream:
                untyped_completion = rag_pipeline.run(
                    query.query,
                    query.filters,
                    query.limit,
                    generation_config=query.generation_config,
                )
                # Tell the type checker that rag_completion is a RAGPipelineOutput
                rag_completion = cast(RAGPipelineOutput, untyped_completion)
                if not rag_completion.completion:
                    raise ValueError(
                        "No completion found in RAGPipelineOutput."
                    )

                completion_text = rag_completion.completion.choices[
                    0
                ].message.content

                # Retrieve the URL dynamically from the request header
                url = request.url
                if not url:
                    url = "http://localhost:8000"
                else:
                    url = str(url).split("/rag_completion")[0]

                # Pass the payload to the /eval endpoint
                payload = {
                    "query": query.query,
                    "context": rag_completion.context or "",
                    "completion_text": completion_text or "",
                    "run_id": str(rag_pipeline.pipeline_run_info["run_id"]),
                    "settings": query.settings.rag_settings.dict(),
                }
                background_tasks.add_task(
                    requests.post, f"{url}/eval", json=payload
                )

                return rag_completion

            else:

                async def _stream_rag_completion(
                    query: RAGQueryModel,
                    rag_pipeline: RAGPipeline,
                ) -> AsyncGenerator[str, None]:
                    gen_config = GenerationConfig(
                        **(query.generation_config.dict())
                    )
                    if not gen_config.stream:
                        raise ValueError(
                            "Must pass `stream` as True to stream completions."
                        )
                    completion_generator = cast(
                        Generator[str, None, None],
                        rag_pipeline.run(
                            query.query,
                            query.filters,
                            query.limit,
                            generation_config=gen_config,
                        ),
                    )

                    search_results = ""
                    context = ""
                    completion_text = ""
                    current_marker = None

                    logging.info(
                        f"Streaming RAG completion results to client for query ={query.query}."
                    )

                    for item in completion_generator:
                        if item.startswith("<"):
                            if item.startswith(
                                f"<{RAGPipeline.SEARCH_STREAM_MARKER}>"
                            ):
                                current_marker = (
                                    RAGPipeline.SEARCH_STREAM_MARKER
                                )
                            elif item.startswith(
                                f"<{RAGPipeline.CONTEXT_STREAM_MARKER}>"
                            ):
                                current_marker = (
                                    RAGPipeline.CONTEXT_STREAM_MARKER
                                )
                            elif item.startswith(
                                f"<{RAGPipeline.COMPLETION_STREAM_MARKER}>"
                            ):
                                current_marker = (
                                    RAGPipeline.COMPLETION_STREAM_MARKER
                                )
                            else:
                                current_marker = None
                        else:
                            if (
                                current_marker
                                == RAGPipeline.SEARCH_STREAM_MARKER
                            ):
                                search_results += item
                            elif (
                                current_marker
                                == RAGPipeline.CONTEXT_STREAM_MARKER
                            ):
                                context += item
                            elif (
                                current_marker
                                == RAGPipeline.COMPLETION_STREAM_MARKER
                            ):
                                completion_text += item
                        yield item

                    # Retrieve the URL dynamically from the request header
                    url = request.url
                    if not url:
                        url = "http://localhost:8000"
                    else:
                        url = str(url).split("/rag_completion")[0]
                        if "localhost" not in url and "127.0.0.1" not in url:
                            url = url.replace("http://", "https://")

                    # Pass the payload to the /eval endpoint
                    payload = {
                        "query": query.query,
                        "context": context,
                        "completion_text": completion_text,
                        "run_id": str(
                            rag_pipeline.pipeline_run_info["run_id"]
                        ),
                        "settings": query.settings.rag_settings.dict(),
                    }
                    logging.info(
                        f"Performing evaluation with payload: {payload} to url: {url}/eval"
                    )
                    background_tasks.add_task(
                        requests.post, f"{url}/eval", json=payload
                    )

                return StreamingResponse(
                    _stream_rag_completion(query, rag_pipeline),
                    media_type="text/plain",
                )
        except Exception as e:
            logging.error(
                f":rag_completion: [Error](query={query}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/eval")
    async def eval(payload: EvalPayloadModel):
        try:
            logging.info(
                f"Received evaluation payload: {payload.dict(exclude_none=True)}"
            )
            query = payload.query
            context = payload.context
            completion_text = payload.completion_text
            run_id = payload.run_id
            settings = payload.settings

            eval_pipeline.run(
                query, context, completion_text, run_id, **(settings.dict())
            )

            return {"message": "Evaluation completed successfully."}
        except Exception as e:
            logging.error(
                f":eval_endpoint: [Error](payload={payload}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/filtered_deletion/")
    async def filtered_deletion(key: str, value: Union[bool, int, str]):
        try:
            embedding_pipeline.db.filtered_deletion(key, value)
            return {"message": "Entries deleted successfully."}
        except Exception as e:
            logging.error(
                f":filtered_deletion: [Error](key={key}, value={value}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/get_user_ids/")
    async def get_user_ids():
        try:
            user_ids = embedding_pipeline.db.get_all_unique_values(
                metadata_field="user_id"
            )
            return {"user_ids": user_ids}
        except Exception as e:
            logging.error(f":get_user_ids: [Error](error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/get_user_documents/")
    async def get_user_documents(user_id: str):
        try:
            document_ids = embedding_pipeline.db.get_all_unique_values(
                metadata_field="document_id", filters={"user_id": user_id}
            )
            return {"document_ids": document_ids}
        except Exception as e:
            logging.error(f":get_user_documents: [Error](error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/logs")
    async def logs():
        try:
            if logging_connection is None:
                raise HTTPException(
                    status_code=404, detail="Logging provider not found."
                )
            logs = logging_connection.get_logs(config.app["max_logs"])
            for log in logs:
                LogModel(**log).dict(by_alias=True)
            return {
                "logs": [LogModel(**log).dict(by_alias=True) for log in logs]
            }
        except Exception as e:
            logging.error(f":logs: [Error](error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/logs_summary")
    async def logs_summary():
        try:
            if logging_connection is None:
                raise HTTPException(
                    status_code=404, detail="Logging provider not found."
                )
            logs = logging_connection.get_logs(config.app["max_logs"])
            logs_summary = process_logs(logs)
            events_summary = [
                SummaryLogModel(**log).dict(by_alias=True)
                for log in logs_summary
            ]
            return {"events_summary": events_summary}

        except Exception as e:
            logging.error(f":logs_summary: [Error](error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    return app
