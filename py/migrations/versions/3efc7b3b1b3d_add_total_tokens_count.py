"""add_total_tokens_to_documents.

Revision ID: 3efc7b3b1b3d
Revises: 7eb70560f406
Create Date: 2025-01-21 14:59:00.000000
"""

import logging
import math
import os

import sqlalchemy as sa
import tiktoken
from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = "3efc7b3b1b3d"
down_revision = "7eb70560f406"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

# Get project name from environment variable, defaulting to 'r2r_default'
project_name = os.getenv("R2R_PROJECT_NAME", "r2r_default")


def count_tokens_for_text(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count the number of tokens in the given text using tiktoken.

    Default model is set to "gpt-3.5-turbo". Adjust if you prefer a different
    model.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback to a known encoding if model not recognized
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def check_if_upgrade_needed() -> bool:
    """Check if the upgrade has already been applied."""
    connection = op.get_bind()
    inspector = inspect(connection)

    # Check if documents table exists in the correct schema
    if not inspector.has_table("documents", schema=project_name):
        logger.info(
            f"Migration not needed: '{project_name}.documents' table doesn't exist"
        )
        return False

    # Check if total_tokens column already exists
    columns = {
        col["name"]
        for col in inspector.get_columns("documents", schema=project_name)
    }

    if "total_tokens" in columns:
        logger.info(
            "Migration not needed: documents table already has total_tokens column"
        )
        return False

    logger.info("Migration needed: documents table needs total_tokens column")
    return True


def upgrade() -> None:
    if not check_if_upgrade_needed():
        return

    connection = op.get_bind()

    # Add the total_tokens column
    logger.info("Adding 'total_tokens' column to 'documents' table...")
    op.add_column(
        "documents",
        sa.Column(
            "total_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        schema=project_name,
    )

    # Process documents in batches
    BATCH_SIZE = 500

    # Count total documents
    logger.info("Determining how many documents need updating...")
    doc_count_query = text(f"SELECT COUNT(*) FROM {project_name}.documents")
    total_docs = connection.execute(doc_count_query).scalar() or 0
    logger.info(f"Total documents found: {total_docs}")

    if total_docs == 0:
        logger.info("No documents found, nothing to update.")
        return

    pages = math.ceil(total_docs / BATCH_SIZE)
    logger.info(
        f"Updating total_tokens in {pages} batches of up to {BATCH_SIZE} documents..."
    )

    default_model = os.getenv("R2R_TOKCOUNT_MODEL", "gpt-3.5-turbo")

    offset = 0
    for page_idx in range(pages):
        logger.info(
            f"Processing batch {page_idx + 1} / {pages} (OFFSET={offset}, LIMIT={BATCH_SIZE})"
        )

        # Fetch next batch of document IDs
        batch_docs_query = text(f"""
            SELECT id
            FROM {project_name}.documents
            ORDER BY id
            LIMIT :limit_val
            OFFSET :offset_val
            """)
        batch_docs = connection.execute(
            batch_docs_query, {"limit_val": BATCH_SIZE, "offset_val": offset}
        ).fetchall()

        if not batch_docs:
            break

        doc_ids = [row["id"] for row in batch_docs]
        offset += BATCH_SIZE

        # Process each document in the batch
        for doc_id in doc_ids:
            chunks_query = text(f"""
                SELECT data
                FROM {project_name}.chunks
                WHERE document_id = :doc_id
                """)
            chunk_rows = connection.execute(
                chunks_query, {"doc_id": doc_id}
            ).fetchall()

            total_tokens = 0
            for c_row in chunk_rows:
                chunk_text = c_row["data"] or ""
                total_tokens += count_tokens_for_text(
                    chunk_text, model=default_model
                )

            # Update total_tokens for this document
            update_query = text(f"""
                UPDATE {project_name}.documents
                SET total_tokens = :tokcount
                WHERE id = :doc_id
                """)
            connection.execute(
                update_query, {"tokcount": total_tokens, "doc_id": doc_id}
            )

        logger.info(f"Finished batch {page_idx + 1}")

    logger.info("Done updating total_tokens.")


def downgrade() -> None:
    """Remove the total_tokens column on downgrade."""
    logger.info(
        "Dropping column 'total_tokens' from 'documents' table (downgrade)."
    )
    op.drop_column("documents", "total_tokens", schema=project_name)
