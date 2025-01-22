"""add_total_tokens_to_documents

Revision ID: 3efc7b3b1b3d
Revises: 7eb70560f406
Create Date: 2025-01-21 14:59:00.000000

"""

import os
import math
import tiktoken
import logging
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "3efc7b3b1b3d"
down_revision = "7eb70560f406"  # Make sure this matches your newest migration
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def count_tokens_for_text(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    Count the number of tokens in the given text using tiktoken.
    Default model is set to "gpt-3.5-turbo". Adjust if you prefer a different model.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to a known encoding if model not recognized
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def upgrade() -> None:
    connection = op.get_bind()

    # 1) Check if column 'total_tokens' already exists in 'documents'
    #    If not, we'll create it with a default of 0.
    #    (If you want the default to be NULL instead of 0, adjust as needed.)
    insp = sa.inspect(connection)
    columns = insp.get_columns("documents")  # uses default schema or your schema
    col_names = [col["name"] for col in columns]
    if "total_tokens" not in col_names:
        logger.info("Adding 'total_tokens' column to 'documents' table...")
        op.add_column(
            "documents", sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0")
        )
    else:
        logger.info("Column 'total_tokens' already exists in 'documents' table, skipping add-column step.")

    # 2) Fill in 'total_tokens' for each document by summing the tokens from all chunks
    #    We do this in batches to avoid loading too much data at once.

    BATCH_SIZE = 500

    # a) Count how many documents we have
    logger.info("Determining how many documents need updating...")
    doc_count_query = text("SELECT COUNT(*) FROM documents")
    total_docs = connection.execute(doc_count_query).scalar() or 0
    logger.info(f"Total documents found: {total_docs}")

    if total_docs == 0:
        logger.info("No documents found, nothing to update.")
        return

    # b) We'll iterate over documents in pages of size BATCH_SIZE
    pages = math.ceil(total_docs / BATCH_SIZE)
    logger.info(f"Updating total_tokens in {pages} batches of up to {BATCH_SIZE} documents...")

    # Optionally choose a Tiktoken model via environment variable
    # or just default if none is set
    default_model = os.getenv("R2R_TOKCOUNT_MODEL", "gpt-3.5-turbo")

    offset = 0
    for page_idx in range(pages):
        logger.info(f"Processing batch {page_idx + 1} / {pages} (OFFSET={offset}, LIMIT={BATCH_SIZE})")

        # c) Fetch the IDs of the next batch of documents
        batch_docs_query = text(
            f"""
            SELECT id
            FROM documents
            ORDER BY id  -- or ORDER BY created_at, if you prefer chronological
            LIMIT :limit_val
            OFFSET :offset_val
            """
        )
        batch_docs = connection.execute(
            batch_docs_query, {"limit_val": BATCH_SIZE, "offset_val": offset}
        ).fetchall()

        # If no results, break early
        if not batch_docs:
            break

        doc_ids = [row["id"] for row in batch_docs]
        offset += BATCH_SIZE

        # d) For each document in this batch, sum up tokens from the chunks table
        for doc_id in doc_ids:
            # Get all chunk text for this doc
            chunks_query = text(
                """
                SELECT data
                FROM chunks
                WHERE document_id = :doc_id
                """
            )
            chunk_rows = connection.execute(chunks_query, {"doc_id": doc_id}).fetchall()

            total_tokens = 0
            for c_row in chunk_rows:
                chunk_text = c_row["data"] or ""
                total_tokens += count_tokens_for_text(chunk_text, model=default_model)

            # e) Update total_tokens for this doc
            update_query = text(
                """
                UPDATE documents
                SET total_tokens = :tokcount
                WHERE id = :doc_id
                """
            )
            connection.execute(update_query, {"tokcount": total_tokens, "doc_id": doc_id})

        logger.info(f"Finished batch {page_idx + 1}")

    logger.info("Done updating total_tokens.")


def downgrade() -> None:
    """
    If you want to remove the total_tokens column on downgrade, do so here.
    Otherwise, you can leave it in place.
    """
    logger.info("Dropping column 'total_tokens' from 'documents' table (downgrade).")
    op.drop_column("documents", "total_tokens")
