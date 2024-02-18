import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from hatchet_sdk import Hatchet
from pydantic import BaseModel

from sciphi_r2r.core import EmbeddingPipeline, RAGPipeline
from sciphi_r2r.main.utils import configure_logging

logger = logging.getLogger("sciphi_r2r")

# Current directory where this script is located
CURRENT_DIR = Path(__file__).resolve().parent


# Function to find the project root by looking for a .git folder or setup.py file
def find_project_root(current_dir):
    for parent in current_dir.parents:
        if any((parent / marker).exists() for marker in [".git", "setup.py"]):
            return parent
    return current_dir  # Fallback to current dir if no marker found


class IngestionSettingsModel(BaseModel):
    do_chunking: Optional[bool] = True


class TextEntryModel(BaseModel):
    id: str
    text: str
    metadata: Optional[dict]


class UpsertTextEntryRequest(BaseModel):
    entry: TextEntryModel
    settings: Optional[IngestionSettingsModel] = IngestionSettingsModel()


class UpsertTextEntriesRequest(BaseModel):
    entries: list[TextEntryModel]
    settings: Optional[IngestionSettingsModel] = IngestionSettingsModel()


class RAGQueryModel(BaseModel):
    query: str
    filters: Optional[dict] = {}
    limit: Optional[int] = 10


def create_app(
    embedding_pipeline: EmbeddingPipeline,
    rag_pipeline: RAGPipeline,
    hatchet: Optional[Hatchet] = None,
    upload_path: Optional[Path] = None,
):
    app = FastAPI()
    configure_logging()

    upload_path = upload_path or find_project_root(CURRENT_DIR) / "uploads"

    if not upload_path.exists():
        upload_path.mkdir()

    @app.post("/upload_and_process_file/")
    async def upload_and_process_file(file: UploadFile = File(...)):
        if not file.filename:
            raise HTTPException(
                status_code=400, detail="No file was uploaded."
            )
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
    def upsert_text_entry(text_entry_req: UpsertTextEntryRequest):
        try:
            if hatchet:
                hatchet.client.event.push(
                    "embedding",
                    {
                        "id": text_entry_req.entry.id,
                        "text": text_entry_req.entry.text,
                        "metadata": text_entry_req.entry.metadata,
                        "settings": (
                            text_entry_req.settings.dict()
                            if text_entry_req.settings
                            else {}
                        ),
                    },
                )
                # TODO: Add an event id to the response
                return {"message": "Upsert initialized successfully."}

            else:
                embedding_pipeline.run(
                    text_entry_req.entry,
                    **(
                        text_entry_req.settings.dict()
                        if text_entry_req.settings
                        else {}
                    ),
                )
                return {"message": "Entry upserted successfully."}
        except Exception as e:
            logger.error(
                f":upsert: [Error](entry={text_entry_req}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upsert_text_entries/")
    def upsert_text_entries(text_entries_req: UpsertTextEntriesRequest):
        embedding_pipeline.run(
            text_entries_req.entries,
            **(
                text_entries_req.settings.dict()
                if text_entries_req.settings
                else {}
            ),
        )

        # try:
        #     if hatchet:
        #         batch = [
        #             {
        #                 "id": entry.id,
        #                 "text": entry.text,
        #                 "metadata": entry.metadata,
        #             }
        #             for entry in text_entries_req.entries
        #         ]
        #         hatchet.client.event.push(
        #             "embedding",
        #             {
        #                 "batch": batch,
        #                 "settings": text_entries_req.settings.dict()
        #                 if text_entries_req.settings
        #                 else {},
        #             },
        #         )
        #         return {"message": "Batch upsert initialized successfully."}

        #     else:
        #         embedding_pipeline.run(
        #             text_entries_req.entries,
        #             **(
        #                 text_entries_req.settings.dict()
        #                 if text_entries_req.settings
        #                 else {}
        #             ),
        #         )
        #         return {"message": "Entries upserted successfully."}
        # except Exception as e:
        #     logger.error(
        #         f":upsert_entries: [Error](entries={text_entries_req}, error={str(e)})"
        #     )
        #     raise HTTPException(status_code=500, detail=str(e))

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
