"""v3_api_database_revision

Revision ID: 8077140e1e99
Revises: 
Create Date: 2024-12-03 12:10:10.878485

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import os


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


def upgrade() -> None:

    # Collections table migration
    op.alter_column(
        f"{project_name}.collections",
        "collection_id",
        new_column_name="id",
    )

    op.drop_column(
        f"{project_name}.collections",
        "kg_enrichment_status",
    )

    op.add_column(
        f"{project_name}.collections",
        sa.Column(
            "owner_id",
            sa.UUID,
            server_default=sa.text("'2acb499e-8428-543b-bd85-0d9098718220'"),
        ),
    )

    op.add_column(
        f"{project_name}.collections",
        sa.Column(
            "graph_sync_status", sa.Text, server_default=sa.text("'pending'")
        ),
    )

    op.add_column(
        f"{project_name}.collections",
        sa.Column(
            "graph_cluster_status",
            sa.Text,
            server_default=sa.text("'pending'"),
        ),
    )

    # Documents table migration
    op.rename_table(
        f"{project_name}.document_info",
        f"{project_name}.documents",
    )

    op.alter_column(
        f"{project_name}.documents",
        "document_id",
        new_column_name="id",
    )

    op.alter_column(
        f"{project_name}.documents",
        "user_id",
        new_column_name="owner_id",
    )

    op.drop_column(
        f"{project_name}.documents",
        "kg_extraction_status",
    )

    op.add_column(
        f"{project_name}.documents",
        sa.Column(
            "extraction_status",
            sa.Text,
            server_default=sa.text("'pending'"),
        ),
    )

    op.alter_column(
        f"{project_name}.documents",
        "doc_search_vector",
        new_column_name="raw_tsvector",
    )

    # Files table migration
    op.rename_table(
        f"{project_name}.file_storage",
        f"{project_name}.files",
    )

    op.alter_column(
        f"{project_name}.files",
        "file_name",
        new_column_name="name",
    )

    op.alter_column(
        f"{project_name}.files",
        "file_oid",
        new_column_name="oid",
    )

    op.alter_column(
        f"{project_name}.files",
        "file_size",
        new_column_name="size",
    )

    op.alter_column(
        f"{project_name}.files",
        "file_type",
        new_column_name="type",
    )

    # Prompts table migration
    op.alter_column(
        f"{project_name}.prompts",
        "prompt_id",
        new_column_name="id",
    )

    # Users table migration
    op.alter_column(
        f"{project_name}.users",
        "user_id",
        new_column_name="id",
    )

    # Chunks table migration
    op.rename_table(
        f"{project_name}.vectors",
        f"{project_name}.chunks",
    )

    op.alter_column(
        f"{project_name}.chunks",
        "extraction_id",
        new_column_name="id",
    )

    op.alter_column(
        f"{project_name}.chunks",
        "user_id",
        new_column_name="owner_id",
    )


def downgrade() -> None:

    # Collections table migration
    op.alter_column(
        f"{project_name}.collections",
        "id",
        new_column_name="collection_id",
    )

    op.add_column(
        f"{project_name}.collections",
        sa.Column(
            "kg_enrichment_status",
            sa.Text,
            server_default=sa.text("'pending'"),
        ),
    )

    op.drop_column(
        f"{project_name}.collections",
        "owner_id",
    )

    op.drop_column(
        f"{project_name}.collections",
        "graph_sync_status",
    )

    op.drop_column(
        f"{project_name}.collections",
        "graph_cluster_status",
    )

    # Documents table migration
    op.rename_table(
        f"{project_name}.documents",
        f"{project_name}.document_info",
    )

    op.alter_column(
        f"{project_name}.document_info",
        "id",
        new_column_name="document_id",
    )

    op.alter_column(
        f"{project_name}.document_info",
        "owner_id",
        new_column_name="user_id",
    )

    op.add_column(
        f"{project_name}.document_info",
        sa.Column(
            "kg_extraction_status",
            sa.Text,
            server_default=sa.text("'pending'"),
        ),
    )

    op.drop_column(
        f"{project_name}.document_info",
        "extraction_status",
    )

    op.alter_column(
        f"{project_name}.document_info",
        "raw_tsvector",
        new_column_name="doc_search_vector",
    )

    # Files table migration
    op.rename_table(
        f"{project_name}.files",
        f"{project_name}.file_storage",
    )

    op.alter_column(
        f"{project_name}.file_storage",
        "name",
        new_column_name="file_name",
    )

    op.alter_column(
        f"{project_name}.file_storage",
        "oid",
        new_column_name="file_oid",
    )

    op.alter_column(
        f"{project_name}.file_storage",
        "size",
        new_column_name="file_size",
    )

    op.alter_column(
        f"{project_name}.file_storage",
        "type",
        new_column_name="file_type",
    )

    # Prompts table migration
    op.alter_column(
        f"{project_name}.prompts",
        "id",
        new_column_name="prompt_id",
    )

    # Users table migration
    op.alter_column(
        f"{project_name}.users",
        "id",
        new_column_name="user_id",
    )

    # Chunks table migration
    op.rename_table(
        f"{project_name}.chunks",
        f"{project_name}.vectors",
    )

    op.alter_column(
        f"{project_name}.vectors",
        "id",
        new_column_name="extraction_id",
    )

    op.alter_column(
        f"{project_name}.vectors",
        "owner_id",
        new_column_name="user_id",
    )
