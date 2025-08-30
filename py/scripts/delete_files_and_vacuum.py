"""Utility script to purge documents by file type and vacuum the database.

The script iterates over a set of file extensions, deletes all documents of each
extension using the REST API, and finally triggers a database vacuum. Example
API call for deleting all `.xlsx` files:

```
curl -X DELETE 'http://localhost:7272/v3/documents/by-filter' \
    -H 'Content-Type: application/json' \
    -d '{"document_type": {"$eq": "xlsx"}}'
```

The vacuum endpoint assumes a maintenance route is exposed at
`POST /v3/maintenance/vacuum`.
"""

import logging
import os
import sys
from typing import Sequence

# Ensure repository root is on the Python path when executed directly.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from r2r import R2RClient

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
            client.documents.delete_by_filter(
                filters={"document_type": {"$eq": file_type}}
            )
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.error("Failed to delete type %s: %s", file_type, exc)


def vacuum_database(client: R2RClient) -> None:
    """Trigger a database vacuum via the maintenance API."""
    try:
        client._make_request("POST", "maintenance/vacuum", version="v3")
        logger.info("Vacuum triggered successfully")
    except Exception as exc:  # pragma: no cover - best effort logging
        logger.error("Vacuum request failed: %s", exc)


def main() -> None:
    base_url = os.getenv("R2R_BASE_URL", "http://localhost:7272")
    client = R2RClient(base_url=base_url)
    delete_documents_by_type(client, FILE_TYPES)
    vacuum_database(client)


if __name__ == "__main__":
    main()
