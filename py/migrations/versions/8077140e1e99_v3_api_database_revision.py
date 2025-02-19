"""v3_api_database_revision.

Revision ID: 8077140e1e99
Revises:
Create Date: 2024-12-03 12:10:10.878485
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "8077140e1e99"
down_revision: Union[str, None] = "2fac23e4d91b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

project_name = os.getenv("R2R_PROJECT_NAME")
if not project_name:
    raise ValueError(
        "Environment variable `R2R_PROJECT_NAME` must be provided migrate, it should be set equal to the value of `project_name` in your `r2r.toml`."
    )


def check_if_upgrade_needed():
    """Check if the upgrade has already been applied or is needed."""
    connection = op.get_bind()
    inspector = inspect(connection)

    # Check collections table column names
    collections_columns = {
        col["name"]
        for col in inspector.get_columns("collections", schema=project_name)
    }

    # If we find a new column name, we don't need to migrate
    # If we find an old column name, we do need to migrate
    if "id" in collections_columns:
        print(
            "Migration not needed: collections table already has 'id' column"
        )
        return False
    elif "collection_id" in collections_columns:
        print("Migration needed: collections table has old column names")
        return True
    else:
        print(
            "Migration not needed: collections table doesn't exist or has different structure"
        )
        return False


def upgrade() -> None:
    if not check_if_upgrade_needed():
        return

    # Collections table migration
    op.alter_column(
        "collections",
        "collection_id",
        new_column_name="id",
        schema=project_name,
    )

    op.drop_column(
        "collections",
        "graph_search_results_enrichment_status",
        schema=project_name,
    )

    op.add_column(
        "collections",
        sa.Column(
            "owner_id",
            sa.UUID,
            server_default=sa.text("'2acb499e-8428-543b-bd85-0d9098718220'"),
        ),
        schema=project_name,
    )

    op.add_column(
        "collections",
        sa.Column(
            "graph_sync_status", sa.Text, server_default=sa.text("'pending'")
        ),
        schema=project_name,
    )

    op.add_column(
        "collections",
        sa.Column(
            "graph_cluster_status",
            sa.Text,
            server_default=sa.text("'pending'"),
        ),
        schema=project_name,
    )

    # Documents table migration
    op.rename_table(
        "document_info",
        "documents",
        schema=project_name,
    )

    op.alter_column(
        "documents",
        "document_id",
        new_column_name="id",
        schema=project_name,
    )

    op.alter_column(
        "documents",
        "user_id",
        new_column_name="owner_id",
        schema=project_name,
    )

    op.drop_column(
        "documents",
        "graph_search_results_extraction_status",
        schema=project_name,
    )

    op.add_column(
        "documents",
        sa.Column(
            "extraction_status",
            sa.Text,
            server_default=sa.text("'pending'"),
        ),
        schema=project_name,
    )

    op.alter_column(
        "documents",
        "doc_search_vector",
        new_column_name="raw_tsvector",
        schema=project_name,
    )

    # Files table migration
    op.rename_table(
        "file_storage",
        "files",
        schema=project_name,
    )

    op.alter_column(
        "files",
        "file_name",
        new_column_name="name",
        schema=project_name,
    )

    op.alter_column(
        "files",
        "file_oid",
        new_column_name="oid",
        schema=project_name,
    )

    op.alter_column(
        "files",
        "file_size",
        new_column_name="size",
        schema=project_name,
    )

    op.alter_column(
        "files",
        "file_type",
        new_column_name="type",
        schema=project_name,
    )

    # Prompts table migration
    op.alter_column(
        "prompts",
        "prompt_id",
        new_column_name="id",
        schema=project_name,
    )

    # Users table migration
    op.alter_column(
        "users",
        "user_id",
        new_column_name="id",
        schema=project_name,
    )

    # Chunks table migration
    op.rename_table(
        "vectors",
        "chunks",
        schema=project_name,
    )

    op.alter_column(
        "chunks",
        "extraction_id",
        new_column_name="id",
        schema=project_name,
    )

    op.alter_column(
        "chunks",
        "user_id",
        new_column_name="owner_id",
        schema=project_name,
    )


def downgrade() -> None:
    # Collections table migration
    op.alter_column(
        "collections",
        "id",
        new_column_name="collection_id",
        schema=project_name,
    )

    op.add_column(
        "collections",
        sa.Column(
            "graph_search_results_enrichment_status",
            sa.Text,
            server_default=sa.text("'pending'"),
        ),
        schema=project_name,
    )

    op.drop_column(
        "collections",
        "owner_id",
        schema=project_name,
    )

    op.drop_column(
        "collections",
        "graph_sync_status",
        schema=project_name,
    )

    op.drop_column(
        "collections",
        "graph_cluster_status",
        schema=project_name,
    )

    # Documents table migration
    op.rename_table(
        "documents",
        "document_info",
        schema=project_name,
    )

    op.alter_column(
        "document_info",
        "id",
        new_column_name="document_id",
        schema=project_name,
    )

    op.alter_column(
        "document_info",
        "owner_id",
        new_column_name="user_id",
        schema=project_name,
    )

    op.add_column(
        "document_info",
        sa.Column(
            "graph_search_results_extraction_status",
            sa.Text,
            server_default=sa.text("'pending'"),
        ),
        schema=project_name,
    )

    op.drop_column(
        "document_info",
        "extraction_status",
        schema=project_name,
    )

    op.alter_column(
        "document_info",
        "raw_tsvector",
        new_column_name="doc_search_vector",
        schema=project_name,
    )

    # Files table migration
    op.rename_table(
        "files",
        "file_storage",
        schema=project_name,
    )

    op.alter_column(
        "file_storage",
        "name",
        new_column_name="file_name",
        schema=project_name,
    )

    op.alter_column(
        "file_storage",
        "oid",
        new_column_name="file_oid",
        schema=project_name,
    )

    op.alter_column(
        "file_storage",
        "size",
        new_column_name="file_size",
        schema=project_name,
    )

    op.alter_column(
        "file_storage",
        "type",
        new_column_name="file_type",
        schema=project_name,
    )

    # Prompts table migration
    op.alter_column(
        "prompts",
        "id",
        new_column_name="prompt_id",
        schema=project_name,
    )

    # Users table migration
    op.alter_column(
        "users",
        "id",
        new_column_name="user_id",
        schema=project_name,
    )

    # Chunks table migration
    op.rename_table(
        "chunks",
        "vectors",
        schema=project_name,
    )

    op.alter_column(
        "vectors",
        "id",
        new_column_name="extraction_id",
        schema=project_name,
    )

    op.alter_column(
        "vectors",
        "owner_id",
        new_column_name="user_id",
        schema=project_name,
    )
