"""Utility script to purge documents by file type.

The script iterates over a set of file extensions, lists all documents of each
extension using the Python client, and deletes each document individually. This
avoids the need for API-key based endpoints and removes the previous database
vacuum step.
"""

import logging
import os
import sys
from typing import Sequence

# Ensure repository root is on the Python path when executed directly.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from r2r import R2RClient, R2RException

# Comprehensive list of supported file types.
FILE_TYPES: list[str] = [
    "doc",
    "docx",
    "odt",
    "pdf",
    "rtf",
    "txt",
    "ppt",
    "pptx",
    "csv",
    "tsv",
    "xls",
    "xlsx",
    "html",
    "md",
    "org",
    "rst",
    "bmp",
    "heic",
    "jpeg",
    "jpg",
    "png",
    "tiff",
    "eml",
    "msg",
    "p7s",
    "epub",
    "json",
]

logger = logging.getLogger(__name__)


def delete_documents_by_type(client: R2RClient, file_types: Sequence[str]) -> None:
    """Delete all documents matching the provided file extensions."""

    for file_type in file_types:
        try:
            logger.info("Deleting documents of type %s", file_type)
            offset = 0
            ids: list[str] = []
            while True:
                resp = client.documents.list(offset=offset, limit=1000)
                documents = resp.results or []
                if not documents:
                    break
                ids.extend(
                    str(doc.id)
                    for doc in documents
                    if doc.document_type.value == file_type
                )
                offset += len(documents)

            for doc_id in ids:
                try:
                    client.documents.delete(doc_id)
                except Exception as exc:  # pragma: no cover - best effort logging
                    logger.error("Failed to delete document %s: %s", doc_id, exc)
        except R2RException as exc:  # pragma: no cover - best effort logging
            if exc.status_code == 401:
                logger.error(
                    "No credentials provided. Set your API key with `r2r configure key` or set the R2R_API_KEY environment variable."
                )
                break
            logger.error("Failed to delete type %s: %s", file_type, exc)
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.error("Failed to delete type %s: %s", file_type, exc)


def main() -> None:
    base_url = os.getenv("R2R_BASE_URL", "http://localhost:7272")
    api_key = os.getenv("R2R_API_KEY")
    if not api_key:
        logger.error(
            "No API key provided. Set R2R_API_KEY or run `r2r configure key` before running this script."
        )
        return

    client = R2RClient(base_url=base_url)
    delete_documents_by_type(client, FILE_TYPES)


if __name__ == "__main__":
    main()
