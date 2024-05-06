import json
import logging
import os
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional, Union, cast

from fastapi import FastAPI

from r2r.core import (
    DocumentParsingPipe,
    EmbeddingPipe,
    EvalPipe,
    LoggingDatabaseConnection,
    RAGPipe,
)
from r2r.main.utils import R2RConfig, apply_cors, find_project_root

from .models import DocumentsIngestorModel

# Current directory where this script is located
CURRENT_DIR = Path(__file__).resolve().parent
MB_CONVERSION_FACTOR = 1024 * 1024


def create_app(
    parsing_pipe: DocumentParsingPipe,
    embedding_pipe: EmbeddingPipe,
    eval_pipe: EvalPipe,
    rag_pipe: RAGPipe,
    config: R2RConfig,
    upload_path: Optional[Path] = None,
    logging_connection: Optional[LoggingDatabaseConnection] = None,
):
    app = FastAPI()
    # TODO - Consider impact of logging in remote environments
    # e.g. such as Google Cloud Run
    apply_cors(app)

    upload_path = upload_path or find_project_root(CURRENT_DIR) / "uploads"

    if not upload_path.exists():
        os.makedirs(upload_path, exist_ok=True)

    @app.post("/ingest_documents/")
    async def ingest_documents(document_request: DocumentsIngestorModel):
        # try:
        # for document in document_request.documents:
        extracted_texts = parsing_pipe.run(
            document_request.documents,
            **document_request.settings.ingestion_settings.dict(),
        )
        # for document in documents:
        #     embedding_pipe.run(
        #         document,
        #         **document_request.settings.embedding_settings.dict(),
        #     )
        return {"message": "Entries upserted successfully."}

    # except Exception as e:
    #     logging.error(
    #         f":add_entries: [Error](document_request={document_request}, error={str(e)})"
    #     )
    #     raise HTTPException(status_code=500, detail=str(e))

    # @app.post("/ingest_file/")
    # # TODO - Add support for multiple files
    # # TODO - Implement a streaming version of this endpoint
    # # TODO - Create request model for this endpoint
    # async def ingest_file(
    #     document_id: str = Form(...),
    #     metadata: str = Form("{}"),
    #     settings: str = Form("{}"),
    #     file: UploadFile = File(...),
    # ):
    #     metadata_json = json.loads(metadata)
    #     settings_model = SettingsModel.parse_raw(settings)

    #     if (
    #         file is not None
    #         and file.size
    #         > config.app.get("max_file_size_in_mb", 100) * MB_CONVERSION_FACTOR
    #     ):
    #         raise HTTPException(
    #             status_code=413,
    #             detail="File size exceeds maximum allowed size.",
    #         )

    #     if not file.filename:
    #         raise HTTPException(
    #             status_code=400, detail="No file was uploaded."
    #         )
    #     # Extract file extension and check if it's an allowed type
    #     file_extension = file.filename.split(".")[-1]
    #     if file_extension not in ingestion_pipe.supported_types:
    #         raise HTTPException(
    #             status_code=400,
    #             detail=f"Invalid file type. Allowed types are: {', '.join(ingestion_pipe.supported_types)}.",
    #         )

    #     file_location = upload_path / file.filename
    #     try:
    #         file_content = file.file.read()

    #         documents = ingestion_pipe.run(
    #             document_id,
    #             {file_extension: file_content},
    #             metadata=metadata_json,
    #             **settings_model.ingestion_settings.dict(),
    #         )

    #         if embedding_pipe.is_async:
    #             await embedding_pipe.run(
    #                 documents, **settings_model.embedding_settings.dict()
    #             )
    #         else:
    #             embedding_pipe.run(
    #                 documents, **settings_model.embedding_settings.dict()
    #             )

    #         return {
    #             "message": f"File '{file.filename}' processed and saved at '{file_location}'"
    #         }
    #     except Exception as e:
    #         logging.error(
    #             f"ingest_file: [Error](file={file.filename}, error={str(e)})"
    #         )
    #         raise HTTPException(status_code=500, detail=str(e))

    # @app.post("/search/")
    # async def search(msg: RAGMessageModel):
    #     try:
    #         rag_completion = rag_pipe.run(
    #             msg.message,
    #             msg.filters,
    #             msg.search_limit,
    #             msg.rerank_limit,
    #             search_only=True,
    #             generation_config=msg.generation_config,
    #         )
    #         return rag_completion.search_results
    #     except Exception as e:
    #         logging.error(
    #             f":search: [Error](message={msg.message}, error={str(e)})"
    #         )
    #         raise HTTPException(status_code=500, detail=str(e))

    # @app.post("/rag_completion/")
    # async def rag_completion(
    #     background_tasks: BackgroundTasks,
    #     msg: RAGMessageModel,
    #     request: Request,
    # ):
    #     try:
    #         stream = msg.generation_config.stream
    #         if not stream:
    #             untyped_completion = rag_pipe.run(
    #                 message=msg.message,
    #                 filters=msg.filters,
    #                 search_limit=msg.search_limit,
    #                 rerank_limit=msg.rerank_limit,
    #                 generation_config=msg.generation_config,
    #             )
    #             # Tell the type checker that rag_completion is a RAGPipeOutput
    #             rag_completion = cast(RAGPipeOutput, untyped_completion)

    #             if not rag_completion.completion:
    #                 if rag_completion.search_results:
    #                     return rag_completion
    #                 raise ValueError(
    #                     "No completion found in RAGPipeOutput."
    #                 )

    #             completion_text = rag_completion.completion.choices[
    #                 0
    #             ].message.content

    #             # Retrieve the URL dynamically from the request header
    #             url = request.url
    #             if not url:
    #                 url = "http://localhost:8000"
    #             else:
    #                 url = str(url).split("/rag_completion")[0]

    #             # Pass the payload to the /eval endpoint
    #             payload = {
    #                 "message": msg.message,
    #                 "context": rag_completion.context or "",
    #                 "completion_text": completion_text or "",
    #                 "run_id": str(rag_pipe.pipe_run_info["run_id"]),
    #                 "settings": msg.settings.rag_settings.dict(),
    #             }
    #             if config.eval.get("sampling_fraction", 0.0) > 0.0:
    #                 background_tasks.add_task(
    #                     requests.post, f"{url}/eval", json=payload
    #                 )

    #             return rag_completion

    #         else:

    #             async def _stream_rag_completion(
    #                 msg: RAGMessageModel,
    #                 rag_pipe: RAGPipe,
    #             ) -> AsyncGenerator[str, None]:
    #                 gen_config = GenerationConfig(
    #                     **(msg.generation_config.dict())
    #                 )
    #                 if not gen_config.stream:
    #                     raise ValueError(
    #                         "Must pass `stream` as True to stream completions."
    #                     )
    #                 completion_generator = cast(
    #                     Generator[str, None, None],
    #                     rag_pipe.run_stream(
    #                         message=msg.message,
    #                         filters=msg.filters,
    #                         search_limit=msg.search_limit,
    #                         rerank_limit=msg.rerank_limit,
    #                         generation_config=gen_config,
    #                     ),
    #                 )

    #                 search_results = ""
    #                 context = ""
    #                 completion_text = ""
    #                 current_marker = None

    #                 logging.info(
    #                     f"Streaming RAG completion results to client for message = {msg.message}."
    #                 )

    #                 for item in completion_generator:
    #                     if item.startswith("<"):
    #                         if item.startswith(
    #                             f"<{RAGPipe.SEARCH_STREAM_MARKER}>"
    #                         ):
    #                             current_marker = (
    #                                 RAGPipe.SEARCH_STREAM_MARKER
    #                             )
    #                         elif item.startswith(
    #                             f"<{RAGPipe.CONTEXT_STREAM_MARKER}>"
    #                         ):
    #                             current_marker = (
    #                                 RAGPipe.CONTEXT_STREAM_MARKER
    #                             )
    #                         elif item.startswith(
    #                             f"<{RAGPipe.COMPLETION_STREAM_MARKER}>"
    #                         ):
    #                             current_marker = (
    #                                 RAGPipe.COMPLETION_STREAM_MARKER
    #                             )
    #                         else:
    #                             current_marker = None
    #                     else:
    #                         if (
    #                             current_marker
    #                             == RAGPipe.SEARCH_STREAM_MARKER
    #                         ):
    #                             search_results += item
    #                         elif (
    #                             current_marker
    #                             == RAGPipe.CONTEXT_STREAM_MARKER
    #                         ):
    #                             context += item
    #                         elif (
    #                             current_marker
    #                             == RAGPipe.COMPLETION_STREAM_MARKER
    #                         ):
    #                             completion_text += item
    #                     yield item

    #                 # Retrieve the URL dynamically from the request header
    #                 url = request.url
    #                 if not url:
    #                     url = "http://localhost:8000"
    #                 else:
    #                     url = str(url).split("/rag_completion")[0]
    #                     if (
    #                         "localhost" not in url
    #                         and "127.0.0.1" not in url
    #                         and "0.0.0.0" not in url
    #                     ):
    #                         url = url.replace("http://", "https://")

    #                 # Pass the payload to the /eval endpoint
    #                 payload = {
    #                     "message": msg.message,
    #                     "context": context,
    #                     "completion_text": completion_text,
    #                     "run_id": str(
    #                         rag_pipe.pipe_run_info["run_id"]
    #                     ),
    #                     "settings": msg.settings.rag_settings.dict(),
    #                 }
    #                 logging.info(
    #                     f"Performing evaluation with payload: {payload} to url: {url}/eval"
    #                 )
    #                 if config.eval.get("sampling_fraction", 0.0) > 0.0:
    #                     background_tasks.add_task(
    #                         requests.post, f"{url}/eval", json=payload
    #                     )

    #             return StreamingResponse(
    #                 _stream_rag_completion(msg, rag_pipe),
    #                 media_type="text/plain",
    #             )
    #     except Exception as e:
    #         logging.error(
    #             f":rag_completion: [Error](message={msg.message}, error={str(e)})"
    #         )
    #         raise HTTPException(status_code=500, detail=str(e))

    # @app.post("/eval")
    # async def eval(payload: EvalPayloadModel):
    #     try:
    #         logging.info(
    #             f"Received evaluation payload: {payload.dict(exclude_none=True)}"
    #         )
    #         message = payload.message
    #         context = payload.context
    #         completion_text = payload.completion_text
    #         run_id = payload.run_id
    #         settings = payload.settings

    #         eval_pipe.run(
    #             message, context, completion_text, run_id, **(settings.dict())
    #         )

    #         return {"message": "Evaluation completed successfully."}

    #     except Exception as e:
    #         logging.error(
    #             f":eval_endpoint: [Error](payload={payload}, error={str(e)})"
    #         )
    #         raise HTTPException(status_code=500, detail=str(e))

    # @app.delete("/delete_by_metadata/")
    # async def delete_by_metadata(
    #     metadata_field: str, metadata_value: Union[bool, int, str]
    # ):
    #     try:
    #         embedding_pipe.vector_db_provider.delete_by_metadata(
    #             metadata_field, metadata_value
    #         )
    #         return {"message": "Entries deleted successfully."}
    #     except Exception as e:
    #         logging.error(
    #             f":delete_by_metadata: [Error](metadata_field={metadata_field}, value={metadata_value}, error={str(e)})"
    #         )
    #         raise HTTPException(status_code=500, detail=str(e))

    # @app.get("/get_user_ids/")
    # async def get_user_ids():
    #     try:
    #         user_ids = (
    #             embedding_pipe.vector_db_provider.get_all_unique_values(
    #                 metadata_field="user_id"
    #             )
    #         )

    #         return {"user_ids": user_ids}
    #     except Exception as e:
    #         logging.error(f":get_user_ids: [Error](error={str(e)})")
    #         raise HTTPException(status_code=500, detail=str(e))

    # @app.get("/get_user_documents/")
    # async def get_user_documents(user_id: str):
    #     try:
    #         document_ids = (
    #             embedding_pipe.vector_db_provider.get_all_unique_values(
    #                 metadata_field="document_id",
    #                 filter_field="user_id",
    #                 filter_value=user_id,
    #             )
    #         )
    #         return {"document_ids": document_ids}
    #     except Exception as e:
    #         logging.error(f":get_user_documents: [Error](error={str(e)})")
    #         raise HTTPException(status_code=500, detail=str(e))

    # @app.get("/logs")
    # async def logs(filter: LogFilterModel = Depends()):
    #     try:
    #         if logging_connection is None:
    #             raise HTTPException(
    #                 status_code=404, detail="Logging provider not found."
    #             )
    #         logs = logging_connection.get_logs(
    #             config.app.get("max_logs", 100), filter.pipe_type
    #         )
    #         for log in logs:
    #             LogModel(**log).dict(by_alias=True)
    #         return {
    #             "logs": [LogModel(**log).dict(by_alias=True) for log in logs]
    #         }
    #     except Exception as e:
    #         logging.error(f":logs: [Error](error={str(e)})")
    #         raise HTTPException(status_code=500, detail=str(e))

    # @app.get("/logs_summary")
    # async def logs_summary(filter: LogFilterModel = Depends()):
    #     try:
    #         if logging_connection is None:
    #             raise HTTPException(
    #                 status_code=404, detail="Logging provider not found."
    #             )
    #         logs = logging_connection.get_logs(
    #             config.app.get("max_logs", 100), filter.pipe_type
    #         )
    #         logs_summary = process_logs(logs)
    #         events_summary = [
    #             SummaryLogModel(**log).dict(by_alias=True)
    #             for log in logs_summary
    #         ]
    #         return {"events_summary": events_summary}

    #     except Exception as e:
    #         logging.error(f":logs_summary: [Error](error={str(e)})")
    #         raise HTTPException(status_code=500, detail=str(e))

    # @app.get("/get_rag_pipe_env_var/")
    # async def get_rag_pipe_env_var():
    #     try:
    #         rag_pipe = os.getenv("RAG_PIPELINE", None)
    #         return {"rag_pipe": rag_pipe}
    #     except Exception as e:
    #         logging.error(f":rag_pipe: [Error](error={str(e)})")
    #         raise HTTPException(status_code=500, detail=str(e))

    # return app
