import json
import logging
import uuid
from typing import Any, AsyncGenerator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.datastructures import UploadFile
from fastapi.param_functions import File, Form

from r2r.core import Document, Pipeline
from r2r.main.utils import apply_cors

# Current directory where this script is located
MB_CONVERSION_FACTOR = 1024 * 1024


async def list_to_generator(array: list[Any]) -> AsyncGenerator[Any, None]:
    for item in array:
        yield item


class R2RApp:
    def __init__(
        self,
        ingestion_pipeline: Pipeline,
        search_pipeline: Pipeline,
        rag_pipeline: Pipeline,
        *args,
        **kwargs,
    ):
        self.app = FastAPI()

        apply_cors(self.app)
        self.ingestion_pipeline = ingestion_pipeline
        self.search_pipeline = search_pipeline
        self.rag_pipeline = rag_pipeline

        self.app.add_api_route(
            path="/ingest_documents/",
            endpoint=self.ingest_documents,
            methods=["POST"],
        )
        self.app.add_api_route(
            path="/ingest_files/", endpoint=self.ingest_files, methods=["POST"]
        )
        self.app.add_api_route(
            path="/search/", endpoint=self.search, methods=["POST"]
        )
        self.app.add_api_route(
            path="/rag/", endpoint=self.rag, methods=["POST"]
        )

    async def ingest_documents(self, documents: list[Document] = Form(...)):
        try:
            # Process the documents through the pipeline
            await self.ingestion_pipeline.run(input=list_to_generator(documents))
            return {"message": "Entries upserted successfully."}
        except Exception as e:
            logging.error(
                f"Error[ingest_documents(documents={documents})]:\n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    async def ingest_files(
        self,
        metadata: str = Form(...),
        ids: list[str] = Form(...),
        files: list[UploadFile] = File(...),
    ):
        try:
            metadata_json = json.loads(metadata)
            results = []
            for file in files:
                if (
                    file.size
                    > 128  # config.app.get("max_file_size_in_mb", 128)
                    * MB_CONVERSION_FACTOR
                ):
                    raise HTTPException(
                        status_code=413,
                        detail="File size exceeds maximum allowed size.",
                    )

                content = await file.read()  # Read file content
                documents = [
                    Document(
                        id=uuid.uuid4()
                        if len(ids) == 0
                        else uuid.UUID(ids[iteration]),
                        type=file.filename.split(".")[-1],
                        data=content,
                        metadata=metadata_json,
                    )
                    for iteration, file in enumerate(files)
                ]
                # Run the pipeline asynchronously
                result = await self.ingestion_pipeline.run(
                    input=list_to_generator(documents)
                )
                results.append(result)
            return {
                "results": [
                    f"File '{file.filename}' processed successfully for each file"
                    for file in files
                ]
            }
        except Exception as e:
            logging.error(
                f"Error[ingest_files(metadata={metadata}, ids={ids}, files={files})]:\n\n{str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    async def search(self, query: str = Form(...)):
        try:
            results = await self.search_pipeline.run(input=query)
            return {"results": results}
        except Exception as e:
            logging.error(f"Error[search(query={query})]:\n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    async def rag(self, query: str = Form(...)):
        try:
            results = await self.rag_pipeline.run(input=query)
            return {"results": results}
        except Exception as e:
            logging.error(f"Error[rag(query={query})]:\n\n{str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    def serve(self, host: str="0.0.0.0", port: int=8000):
        try:
            import uvicorn
        except ImportError:
            raise ImportError("Please install uvicorn using 'pip install uvicorn'")
        
        uvicorn.run(self.app, host=host, port=port)