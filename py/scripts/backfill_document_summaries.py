import asyncio
import logging
import os
import sys

# Ensure the repository's Python package path is available when executing as a script.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.base import DocumentResponse
from core.main.assembly.builder import R2RBuilder
from core.main.config import R2RConfig

logger = logging.getLogger(__name__)


def _chunk_records_to_dicts(results: list[dict]) -> list[dict]:
    """Translate chunk records from the database into the format expected by
    IngestionService.augment_document_info."""
    chunk_dicts = []
    for r in results:
        chunk_dicts.append(
            {
                "id": r["id"],
                "document_id": r["document_id"],
                "owner_id": r["owner_id"],
                "collection_ids": r["collection_ids"],
                "data": r["text"],
                "metadata": r["metadata"],
            }
        )
    return chunk_dicts


async def backfill_document_summaries() -> None:
    """Generate and store summaries for documents lacking one."""
    config = R2RConfig.load()
    # `backfill_document_summaries` runs as a one-off maintenance script and
    # does not require the distributed Hatchet orchestrator. Some config
    # presets (e.g. "full") enable the Hatchet provider by default which in
    # turn expects the `HATCHET_CLIENT_TOKEN` environment variable to be set.
    # When the token is absent the script would previously crash during
    # provider creation. Fallback to the lightweight "simple" orchestration
    # provider unless the token is available so Hatchet can be used when
    # desired.
    if not os.getenv("HATCHET_CLIENT_TOKEN"):
        logger.info(
            "HATCHET_CLIENT_TOKEN not set; using simple orchestration provider"
        )
        config.orchestration.provider = "simple"

    builder = R2RBuilder(config)
    app = await builder.build()

    ingestion_service = app.services.ingestion
    providers = app.providers

    # Fetch all documents missing a summary (NULL or empty string).
    docs_resp = (
        await providers.database.documents_handler.get_documents_overview(
            offset=0,
            limit=-1,
            filters={
                "$or": [
                    {"summary": {"$eq": None}},
                    {"summary": {"$eq": ""}},
                ]
            },
        )
    )
    documents: list[DocumentResponse] = docs_resp["results"]

    for doc in documents:
        logger.info("Processing document %s", doc.id)
        chunks_resp = (
            await providers.database.chunks_handler.list_document_chunks(
                document_id=doc.id,
                offset=0,
                limit=-1,
            )
        )
        chunk_dicts = _chunk_records_to_dicts(chunks_resp["results"])
        if not chunk_dicts:
            logger.info("Skipping %s; no chunks found", doc.id)
            continue

        await ingestion_service.augment_document_info(doc, chunk_dicts)
        await providers.database.documents_handler.upsert_documents_overview(
            doc
        )

    await providers.database.close()


if __name__ == "__main__":
    asyncio.run(backfill_document_summaries())
