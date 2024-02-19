import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from sciphi_r2r.core import EmbeddingPipeline, IngestionPipeline, RAGPipeline
from sciphi_r2r.main.utils import configure_logging, find_project_root

logger = logging.getLogger("sciphi_r2r")

# Current directory where this script is located
CURRENT_DIR = Path(__file__).resolve().parent

# Define the types of entries that can be ingested


class EntryType(str, Enum):
    json = "json"
    txt = "txt"
    html = "html"


class EntryModel(BaseModel):
    document_id: str
    blob: str
    type: EntryType
    metadata: Optional[dict]


# TODO - Rename and restructure settings model
class IngestionSettingsModel(BaseModel):
    do_chunking: Optional[bool] = True


class UpsertEntryRequest(BaseModel):
    entry: EntryModel
    settings: Optional[IngestionSettingsModel] = IngestionSettingsModel()


class UpsertEntriesRequest(BaseModel):
    entries: list[EntryModel]
    settings: Optional[IngestionSettingsModel] = IngestionSettingsModel()


class RAGQueryModel(BaseModel):
    query: str
    filters: Optional[dict] = {}
    limit: Optional[int] = 10


def create_app(
    ingestion_pipeline: IngestionPipeline,
    embedding_pipeline: EmbeddingPipeline,
    rag_pipeline: RAGPipeline,
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

        # Extract file extension and check if it's an allowed type
        file_extension = file.filename.split(".")[-1]
        if file_extension not in EntryType._value2member_map_:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types are: {', '.join(EntryType._value2member_map_.keys())}.",
            )

        file_location = upload_path / file.filename
        try:
            # Save the file to disk
            with open(file_location, "wb+") as file_object:
                file_content = file.file.read()
                file_object.write(file_content)

            # Process the file content based on its type
            if file_extension == EntryType.txt.value:
                text = file_content.decode("utf-8")
                # Process plain text
            elif file_extension == EntryType.json.value:
                # Process JSON
                pass  # You would add JSON processing logic here
            elif file_extension == EntryType.html.value:
                # Process HTML
                pass  # You would add HTML processing logic here

            return {
                "message": f"File '{file.filename}' processed and saved at '{file_location}'"
            }
        except Exception as e:
            logger.error(
                f"upload_and_process_file: [Error](file={file.filename}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upsert_entry/")
    def upsert_entry(entry_req: UpsertEntryRequest):
        try:
            embedding_settings = (
                entry_req.settings.dict() if entry_req.settings else {}
            )

            document = ingestion_pipeline.run(
                entry_req.entry.document_id,
                entry_req.entry.blob,
                entry_req.entry.type,
                metadata=entry_req.entry.metadata,
                is_file=False,
            )
            embedding_pipeline.run(document, **embedding_settings)
            return {"message": "Entry upserted successfully."}
        except Exception as e:
            logger.error(
                f":upsert_entry: [Error](entry={entry_req}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/upsert_entries/")
    def upsert_entries(entries_req: UpsertEntriesRequest):
        try:
            embedding_settings = (
                entries_req.settings.dict() if entries_req.settings else {}
            )
            for entry in entries_req.entries:
                document = ingestion_pipeline.run(
                    entry.document_id,
                    entry.blob,
                    entry.type,
                    metadata=entry.metadata,
                    is_file=False,
                )
                embedding_pipeline.run(document, **embedding_settings)
            return {"message": "Entries upserted successfully."}
        except Exception as e:
            logger.error(
                f":upsert_entries: [Error](entries={entries_req}, error={str(e)})"
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

    @app.delete("/filtered_deletion/")
    def filtered_deletion(key: str, value: Union[bool, int, str]):
        try:
            # Assuming you have a filtered_deletion method in your ingestion pipeline
            embedding_pipeline.db.filtered_deletion(key, value)
            return {"message": "Entries deleted successfully."}
        except Exception as e:
            logger.error(
                f":filtered_deletion: [Error](key={key}, value={value}, error={str(e)})"
            )
            raise HTTPException(status_code=500, detail=str(e))

    return app
