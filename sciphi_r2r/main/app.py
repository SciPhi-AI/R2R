import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from sciphi_r2r.core import (EmbeddingPipeline, LoggingDatabaseConnection,
                             RAGPipeline, VectorEntry)
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
            embedding = embedding_pipeline.embeddings_provider.get_embedding(
                entry.text, embedding_pipeline.embedding_model
            )
            vector_entry = {
                "entry_id": entry.id,
                "vector": embedding,
                "metadata": entry.metadata,
            }
            embedding_pipeline.db.upsert(VectorEntry(**vector_entry))
            return {"message": "Entry upserted successfully."}
        except Exception as e:
            logger.error(f":upsert: [Error](entry={entry}, error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upsert_entries/")
    def upsert_entries(entries: list[RawEntryModel]):
        try:
            vector_entries = []
            for entry in entries.entries:
                embedding = (
                    embedding_pipeline.embeddings_provider.get_embedding(
                        entry.text, embedding_pipeline.embedding_model
                    )
                )
                vector_entry = {
                    "entry_id": entry.id,
                    "vector": embedding,
                    "metadata": entry.metadata,
                }
                vector_entries.append(VectorEntry(**vector_entry))
            embedding_pipeline.db.upsert_entries(vector_entries)

            return {"message": "Entries upserted successfully."}
        except Exception as e:
            logger.error(f":upsert_entries: [Error](entries={entries}, error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/search/")
    def search(query: RAGQueryModel):
        try:
            rag_completion = rag_pipeline.run(
                query.query, query.filters, query.limit, search_only=True
            )
            return rag_completion
        except Exception as e:
            logger.error(f":search: [Error](query={query}, error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/rag_completion/")
    def rag_completion(query: RAGQueryModel):
        try:
            rag_completion = rag_pipeline.run(
                query.query, query.filters, query.limit
            )
            return rag_completion
        except Exception as e:
            logger.error(
                f":rag_completion: [Error](query={query}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    return app
