"""Add user and document count to collection.

Revision ID: c45a9cf6a8a4
Revises: 8077140e1e99
Create Date: 2024-12-10 13:28:07.798167
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "c45a9cf6a8a4"
down_revision: Union[str, None] = "8077140e1e99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

project_name = os.getenv("R2R_PROJECT_NAME")
if not project_name:
    raise ValueError(
        "Environment variable `R2R_PROJECT_NAME` must be provided migrate, it should be set equal to the value of `project_name` in your `r2r.toml`."
    )


def check_if_upgrade_needed():
    """Check if the upgrade has already been applied."""
    connection = op.get_bind()
    inspector = inspect(connection)

    collections_columns = {
        col["name"]
        for col in inspector.get_columns("collections", schema=project_name)
    }

    if "user_count" in collections_columns:
        print(
            "Migration not needed: collections table already has count columns"
        )
        return False
    else:
        print("Migration needed: collections table needs count columns")
        return True


def upgrade():
    if not check_if_upgrade_needed():
        return

    # Add the new columns with default value of 0
    op.add_column(
        "collections",
        sa.Column(
            "user_count", sa.Integer(), nullable=False, server_default="0"
        ),
        schema=project_name,
    )
    op.add_column(
        "collections",
        sa.Column(
            "document_count", sa.Integer(), nullable=False, server_default="0"
        ),
        schema=project_name,
    )

    # Initialize the counts based on existing relationships
    op.execute(f"""
        WITH collection_counts AS (
            SELECT c.id,
                   COUNT(DISTINCT u.id) as user_count,
                   COUNT(DISTINCT d.id) as document_count
            FROM {project_name}.collections c
            LEFT JOIN {project_name}.users u ON c.id = ANY(u.collection_ids)
            LEFT JOIN {project_name}.documents d ON c.id = ANY(d.collection_ids)
            GROUP BY c.id
        )
        UPDATE {project_name}.collections c
        SET user_count = COALESCE(cc.user_count, 0),
            document_count = COALESCE(cc.document_count, 0)
        FROM collection_counts cc
        WHERE c.id = cc.id
    """)


def downgrade():
    op.drop_column("collections", "document_count", schema=project_name)
    op.drop_column("collections", "user_count", schema=project_name)
