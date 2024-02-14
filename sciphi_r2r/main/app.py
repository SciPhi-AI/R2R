import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from sciphi_r2r.core import EmbeddingPipeline, RAGPipeline
from sciphi_r2r.main.utils import configure_logging

from hatchet_sdk import Hatchet

logger = logging.getLogger("sciphi_r2r")

# Current directory where this script is located
CURRENT_DIR = Path(__file__).resolve().parent


# Function to find the project root by looking for a .git folder or setup.py file
def find_project_root(current_dir):
    for parent in current_dir.parents:
        if any((parent / marker).exists() for marker in [".git", "setup.py"]):
            return parent
    return current_dir  # Fallback to current dir if no marker found


class TextEntryModel(BaseModel):
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
    hatchet: Hatchet,
    upload_path: Optional[Path] = None,
):
    app = FastAPI()
    configure_logging()

    if not upload_path:
        upload_path = find_project_root(CURRENT_DIR) / "uploads"

    if not upload_path.exists():
        upload_path.mkdir()

    @app.post("/upload_and_process_file/")
    async def upload_and_process_file(file: UploadFile = File(...)):
        # Check if the file is a .txt file
        if not file.filename.endswith(".txt"):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only .txt files are allowed.",
            )

        file_location = upload_path / file.filename
        try:
            # Save the file to disk
            with open(file_location, "wb+") as file_object:
                file_content = file.file.read()
                file_object.write(file_content)

            # Process the file content
            text = file_content.decode("utf-8")
            text_entry = TextEntryModel(
                id="generated_id", text=text, metadata={}
            )
            embedding_pipeline.run(text_entry)

            return {
                "message": f"File '{file.filename}' processed and saved at '{file_location}'"
            }
        except Exception as e:
            logger.error(
                f"upload_and_process_file: [Error](file={file.filename}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upsert_text_entry/")
    def upsert_text_entry(text_entry: TextEntryModel):
        try:
            # TODO: case on whether Hatchet exists or not
            hatchet.client.event.push("embedding", {"id": text_entry.id, "text": text_entry.text, "metadata": text_entry.metadata})

            # embedding_pipeline.run(text_entry)

            return {"message": "Entry upserted successfully."}
        except Exception as e:
            logger.error(
                f":upsert: [Error](entry={text_entry}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upsert_text_entries/")
    def upsert_text_entries(entries: list[TextEntryModel]):
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

    return app
