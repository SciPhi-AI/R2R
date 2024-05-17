import json
import logging
import uuid
from typing import Any, AsyncGenerator, List, Optional, Union

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from r2r.core import (
    Document,
    DocumentType,
    GenerationConfig,
    Pipeline,
    PipeLoggingConnectionSingleton,
    R2RConfig,
    generate_id_from_label,
)

from .factory import R2RProviders

MB_CONVERSION_FACTOR = 1024 * 1024

from pydantic import BaseModel


async def list_to_generator(array: list[Any]) -> AsyncGenerator[Any, None]:
    for item in array:
        yield item


class R2RApp:
    def __init__(
        self,
        config: R2RConfig,
        providers: R2RProviders,
        ingestion_pipeline: Pipeline,
        search_pipeline: Pipeline,
        rag_pipeline: Pipeline,
        streaming_rag_pipeline: Pipeline,
        do_apply_cors: bool = True,
        *args,
        **kwargs,
    ):
        self.config = config
        self.providers = providers
        self.logging_connection = PipeLoggingConnectionSingleton()
        self.ingestion_pipeline = ingestion_pipeline
        self.search_pipeline = search_pipeline
        self.rag_pipeline = rag_pipeline
        self.streaming_rag_pipeline = streaming_rag_pipeline

        self.app = FastAPI()
        if do_apply_cors:
            R2RApp._apply_cors(self.app)

        self.app.add_api_route(
            path="/ingest_documents/",
            endpoint=self.ingest_documents_wrapper,
            methods=["POST"],
        )
        self.app.add_api_route(
            path="/ingest_files/",
            endpoint=self.ingest_files_wrapper,
            methods=["POST"],
        )
        self.app.add_api_route(
            path="/search/", endpoint=self.search_wrapper, methods=["POST"]
        )
        self.app.add_api_route(
            path="/rag/", endpoint=self.rag_wrapper, methods=["POST"]
        )
        self.app.add_api_route(
            path="/delete/", endpoint=self.delete_wrapper, methods=["DELETE"]
        )
        self.app.add_api_route(
            path="/get_user_ids/",
            endpoint=self.get_user_ids_wrapper,
            methods=["GET"],
        )
        self.app.add_api_route(
            path="/get_user_document_data/",
            endpoint=self.get_user_document_data_wrapper,
            methods=["POST"],
        )
        self.app.add_api_route(
            path="/get_logs/",
            endpoint=self.get_logs_wrapper,
            methods=["POST"],
        )

    async def ingest_documents(self, documents: List[Document]):
        try:
            # Process the documents through the pipeline
            await self.ingestion_pipeline.run(
                input=list_to_generator(documents), pipeline_type="ingestion"
            )
            return {"results": "Entries upserted successfully."}
        except Exception as e:
            logging.error(
                f"ingest_documents(documents={documents}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    class IngestDocumentsRequest(BaseModel):
        documents: List[Document]

    async def ingest_documents_wrapper(self, request: IngestDocumentsRequest):
        return await self.ingest_documents(request.documents)

    async def ingest_files(
        self,
        metadatas: str = "[{}]",
        ids: str = "[]",
        files: list[UploadFile] = [],
    ):
        try:
            ids_list = json.loads(ids)
            metadata_jsons = json.loads(metadatas)
            documents = []
            for iteration, file in enumerate(files):
                if (
                    file.size
                    > self.config.app.get("max_file_size_in_mb", 32)
                    * MB_CONVERSION_FACTOR
                ):
                    raise HTTPException(
                        status_code=413,
                        detail="File size exceeds maximum allowed size.",
                    )
                if not file.filename:
                    raise HTTPException(
                        status_code=400, detail="File name not provided."
                    )
                documents.append(
                    Document(
                        id=generate_id_from_label(file.filename)
                        if len(ids_list) == 0
                        else uuid.UUID(ids_list[iteration]),
                        type=DocumentType(file.filename.split(".")[-1]),
                        data=await file.read(),
                        metadata=metadata_jsons[iteration],
                    )
                )
            # Run the pipeline asynchronously
            await self.ingestion_pipeline.run(
                input=list_to_generator(documents),
                pipeline_type="ingestion",
            )
            return {
                "results": [
                    f"File '{file.filename}' processed successfully for each file"
                    for file in files
                ]
            }
        except Exception as e:
            logging.error(
                f"ingest_files(metadata={metadatas}, ids={ids}, files={files}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    async def ingest_files_wrapper(
        self,
        metadatas: str = Form(...),
        ids: str = Form(...),
        files: List[UploadFile] = File(...),
    ):
        return await self.ingest_files(metadatas, ids, files)

    async def search(
        self,
        query: str = "",
        search_filters: str = "{}",
        search_limit: int = 10,
    ):
        try:
            json_search_filters = json.loads(search_filters)
            results = await self.search_pipeline.run(
                input=list_to_generator([query]),
                search_filters=json_search_filters,
                search_limit=search_limit,
            )
            return {"results": [results.dict() for results in results]}
        except Exception as e:
            logging.error(f"search(query={query}) - \n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    class SearchRequest(BaseModel):
        query: str
        search_filters: Optional[str]
        search_limit: int = 10

    async def search_wrapper(self, request: SearchRequest):
        return await self.search(
            request.query, request.search_filters, request.search_limit
        )

    async def rag(
        self,
        message: str = "",
        search_filters: Optional[dict[str, str]] = None,
        search_limit: int = 10,
        generation_config: Optional[GenerationConfig] = None,
        streaming: bool = False,
    ):
        try:
            if streaming or (generation_config and generation_config.stream):

                async def stream_response():
                    async for chunk in await self.streaming_rag_pipeline.run(
                        input=list_to_generator([message]),
                        streaming=True,
                        search_filters=search_filters,
                        search_limit=search_limit,
                        generation_config=generation_config,
                    ):
                        yield chunk

                return StreamingResponse(
                    stream_response(), media_type="application/json"
                )
            else:
                results = await self.rag_pipeline.run(
                    input=list_to_generator([message]),
                    search_filters=search_filters,
                    search_limit=search_limit,
                    generation_config=generation_config,
                )
                return {"results": results}
        except Exception as e:
            logging.error(f"rag(message={message}) - \n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    class RAGRequest(BaseModel):
        message: str
        search_filters: Optional[str]
        search_limit: int = 10
        generation_config: Optional[str] = None
        streaming: bool = False

    async def rag_wrapper(self, request: RAGRequest):
        search_filters_dict = (
            json.loads(request.search_filters)
            if request.search_filters
            else None
        )
        GenerationConfig(
            **json.loads(request.generation_config)
            if request.generation_config
            else {}
        )
        return await self.rag(
            request.message,
            search_filters_dict,
            request.search_limit,
            request.generation_config,
            request.streaming,
        )

    async def delete(self, key: str, value: Union[bool, int, str]):
        try:
            self.providers.vector_db.delete_by_metadata(key, value)
            return {"results": "Entries deleted successfully."}
        except Exception as e:
            logging.error(
                f":delete: [Error](key={key}, value={value}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    class DeleteRequest(BaseModel):
        key: str
        value: Union[bool, int, str]

    async def delete_wrapper(self, request: DeleteRequest = Body(...)):
        return await self.delete(request.key, request.value)

    async def get_user_ids(self):
        try:
            user_ids = self.providers.vector_db.get_metadatas(
                metadata_fields=["user_id"]
            )

            return {"results": [ele["user_id"] for ele in user_ids]}
        except Exception as e:
            logging.error(f"get_user_ids() - \n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    async def get_user_ids_wrapper(self):
        return await self.get_user_ids()

    async def get_user_document_data(self, user_id: str):
        try:
            if isinstance(user_id, uuid.UUID):
                user_id = str(user_id)
            document_ids = self.providers.vector_db.get_metadatas(
                metadata_fields=["document_id", "title"],
                filter_field="user_id",
                filter_value=user_id,
            )
            return {"results": [ele for ele in document_ids]}
        except Exception as e:
            logging.error(
                f"get_user_document_data(user_id={user_id}) - \n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    class UserDocumentRequest(BaseModel):
        user_id: str

    async def get_user_document_data_wrapper(
        self, request: UserDocumentRequest
    ):
        return await self.get_user_document_data(request.user_id)

    async def get_logs(self, pipeline_type: Optional[str] = None):
        try:
            logs_per_run = 10
            if self.logging_connection is None:
                raise HTTPException(
                    status_code=404, detail="Logging provider not found."
                )
            run_info = await self.logging_connection.get_run_info(
                pipeline_type=pipeline_type,
                limit=self.config.app.get("max_logs", 100) // logs_per_run,
            )
            logs = await self.logging_connection.get_logs(
                [run.run_id for run in run_info]
            )
            # Aggregate logs by run_id and include run_type
            aggregated_logs = []

            for run in run_info:
                run_logs = [
                    log for log in logs if log["pipe_run_id"] == run.run_id
                ]
                entries = [
                    {"key": log["key"], "value": log["value"]}
                    for log in run_logs
                ]
                aggregated_logs.append(
                    {
                        "run_id": run.run_id,
                        "run_type": run.pipeline_type,
                        "entries": entries,
                    }
                )

            return {"results": aggregated_logs}

        except Exception as e:
            logging.error(f":logs: [Error](error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    class LogsRequest(BaseModel):
        pipeline_type: Optional[str] = None

    async def get_logs_wrapper(self, request: LogsRequest):
        return await self.get_logs(request.pipeline_type)

    def serve(self, host: str = "0.0.0.0", port: int = 8000):
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "Please install uvicorn using 'pip install uvicorn'"
            )

        uvicorn.run(self.app, host=host, port=port)

    @staticmethod
    def _apply_cors(app):
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
