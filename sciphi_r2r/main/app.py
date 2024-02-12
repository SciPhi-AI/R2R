import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from sciphi_r2r.core import EmbeddingPipeline, RAGPipeline
from sciphi_r2r.main.utils import configure_logging

logger = logging.getLogger("sciphi_r2r")


class RawEntryModel(BaseModel):
    id: str
    text: str
    metadata: Optional[dict]


class RAGQueryModel(BaseModel):
    query: str
    filters: Optional[dict] = {}
    limit: Optional[int] = 10


def create_app(
    embedding_pipeline: EmbeddingPipeline,
    rag_pipeline: RAGPipeline,
):
    app = FastAPI()
    configure_logging()

    @app.post("/upsert/")
    def upsert_entry(entry: RawEntryModel):
        try:
            embedding_pipeline.run(entry)
            return {"message": "Entry upserted successfully."}
        except Exception as e:
            logger.error(f":upsert: [Error](entry={entry}, error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upsert_entries/")
    def upsert_entries(entries: list[RawEntryModel]):
        try:
            embedding_pipeline.run(entries)
            return {"message": "Entries upserted successfully."}
        except Exception as e:
            logger.error(
                f":upsert_entries: [Error](entries={entries}, error={str(e)})"
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

    @app.post("/completion/")
    def completion(query: RAGQueryModel):
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

    return app
