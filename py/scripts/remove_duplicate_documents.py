"""Remove duplicate documents based on metadata SHA-256 hash.

The script fetches all documents from the database, groups them by the
`metadata['sha256']` field and deletes all but one document for each hash.
"""

import asyncio
import logging
import os
import sys

# Ensure repository root is on the Python path when executed directly.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.base import DocumentResponse
from core.main.assembly.builder import R2RBuilder
from core.main.config import R2RConfig

logger = logging.getLogger(__name__)


async def remove_duplicate_documents() -> None:
    """Delete duplicate documents sharing the same SHA-256 hash."""
    config = R2RConfig.load()
    if not os.getenv("HATCHET_CLIENT_TOKEN"):
        logger.info(
            "HATCHET_CLIENT_TOKEN not set; using simple orchestration provider"
        )
        config.orchestration.provider = "simple"

    builder = R2RBuilder(config)
    app = await builder.build()
    providers = app.providers

    resp = await providers.database.documents_handler.get_documents_overview(
        offset=0,
        limit=-1,
    )
    documents: list[DocumentResponse] = resp["results"]

    seen: dict[str, DocumentResponse] = {}
    duplicates: list[DocumentResponse] = []

    for doc in documents:
        sha256 = doc.metadata.get("sha256")
        if not sha256:
            continue
        if sha256 in seen:
            duplicates.append(doc)
        else:
            seen[sha256] = doc

    for doc in duplicates:
        logger.info("Deleting duplicate document %s", doc.id)
        await providers.database.documents_handler.delete(doc.id, doc.version)

    logger.info("Deleted %d duplicate documents", len(duplicates))
    await providers.database.close()


if __name__ == "__main__":
    asyncio.run(remove_duplicate_documents())
