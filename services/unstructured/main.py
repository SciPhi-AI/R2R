import asyncio
import base64
import concurrent.futures
import logging
import os
from io import BytesIO
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from unstructured.partition.auto import partition

logger = logging.getLogger()

app = FastAPI()


class PartitionRequestModel(BaseModel):
    file_content: bytes
    ingestion_config: dict
    filename: Optional[str] = None


class PartitionResponseModel(BaseModel):
    elements: list[dict]


executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.environ.get("MAX_INGESTION_WORKERS", 10))
)


def run_partition(file_content: str, filename: str, ingestion_config: dict) -> list[dict]:
    file_content_bytes = base64.b64decode(file_content)
    file_io = BytesIO(file_content_bytes)
    elements = partition(file=file_io, file_filename=filename, **ingestion_config)
    return [element.to_dict() for element in elements]


@app.get("/health")
async def health_endpoint():
    return {"status": "ok"}


@app.post("/partition", response_model=PartitionResponseModel)
async def partition_endpoint(request: PartitionRequestModel):
    try:
        logger.info(f"Partitioning request received: {request}")
        loop = asyncio.get_event_loop()
        elements = await loop.run_in_executor(
            executor,
            run_partition,
            request.file_content,
            request.filename,
            request.ingestion_config,
        )
        logger.info("Partitioning completed")
        return PartitionResponseModel(elements=elements)
    except Exception as e:
        logger.error(f"Error partitioning file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
