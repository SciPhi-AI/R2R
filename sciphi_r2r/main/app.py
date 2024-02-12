import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from sciphi_r2r.core import RAGPipeline, EmbeddingPipeline, VectorEntry
from sciphi_r2r.main.utils import configure_logging

logger = logging.getLogger("sciphi_r2r")


class VectorEntryModel(BaseModel):
    id: str
    vector: list[float]
    metadata: Optional[dict]


class SearchQueryModel(BaseModel):
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
    def upsert_entry(entry: VectorEntryModel):
        try:
            embedding_pipeline.db.upsert(VectorEntry(**entry.dict()))
            return {"message": "Entry upserted successfully."}
        except Exception as e:
            logger.error(f":upsert: [Error](entry.id={entry.id}) - {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upsert_entries/")
    def upsert_entries(entries: list[VectorEntryModel]):
        try:
            embedding_pipeline.db.upsert_entries(
                [VectorEntry(**entry.dict()) for entry in entries]
            )
            return {"message": "Entries upserted successfully."}
        except Exception as e:
            logger.error(f":upsert_entries: [Error]({entries})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/search/")
    def search(query: SearchQueryModel):
        try:
            query_vector = (
                embedding_pipeline.embeddings_provider.get_embedding(
                    query.query, embedding_pipeline.embedding_model
                )
            )
            search_results = embedding_pipeline.db.search(
                query_vector=query_vector, **query.dict()
            )
            return search_results
        except Exception as e:
            logger.info(f":search: [Error](query={query})")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/rag_completion/")
    def rag_completion(query: SearchQueryModel):
        try:
            rag_completion = rag_pipeline.run(
                query.query, query.filters, query.limit
            )
            return rag_completion
        except Exception as e:
            logger.info(f":rag_completion: [Error](query={query}, error={str(e)})")
            raise HTTPException(status_code=500, detail=str(e))

    return app
