"""migrate_to_asyncpg

Revision ID: d342e632358a
Revises:
Create Date: 2024-10-22 11:55:49.461015

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import UserDefinedType

# revision identifiers, used by Alembic.
revision: str = "d342e632358a"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


project_name = "r2r-test"  # Replace with your actual project name

new_vector_table_name = "vectors"
old_vector_table_name = project_name


class Vector(UserDefinedType):
    def get_col_spec(self, **kw):
        return "vector"


def upgrade() -> None:
    # Create required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gin")

    # Create the new table
    op.create_table(
        new_vector_table_name,
        sa.Column("extraction_id", postgresql.UUID(), nullable=False),
        sa.Column("document_id", postgresql.UUID(), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=False),
        sa.Column(
            "collection_ids",
            postgresql.ARRAY(postgresql.UUID()),
            server_default="{}",
        ),
        sa.Column("vec", Vector),  # This will be handled as a vector type
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column(
            "fts",
            postgresql.TSVECTOR,
            nullable=False,
            server_default=sa.text("to_tsvector('english'::regconfig, '')"),
        ),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default="{}", nullable=False
        ),
        sa.PrimaryKeyConstraint("extraction_id"),
        schema=project_name,
    )

    # Create indices
    op.create_index(
        "idx_vectors_document_id",
        new_vector_table_name,
        ["document_id"],
        schema=project_name,
    )

    op.create_index(
        "idx_vectors_user_id",
        new_vector_table_name,
        ["user_id"],
        schema=project_name,
    )

    op.create_index(
        "idx_vectors_collection_ids",
        new_vector_table_name,
        ["collection_ids"],
        schema=project_name,
        postgresql_using="gin",
    )

    op.create_index(
        "idx_vectors_fts",
        new_vector_table_name,
        ["fts"],
        schema=project_name,
        postgresql_using="gin",
    )

    # Migrate data from old table (assuming old table name is 'old_vectors')
    # Note: You'll need to replace 'old_schema' and 'old_vectors' with your actual names
    op.execute(
        f"""
        INSERT INTO {project_name}.{new_vector_table_name}
            (extraction_id, document_id, user_id, collection_ids, vec, text, metadata)
        SELECT
            extraction_id,
            document_id,
            user_id,
            collection_ids,
            vec,
            text,
            metadata
        FROM {project_name}.{old_vector_table_name}
    """
    )


def downgrade() -> None:
    # Drop all indices
    op.drop_index("idx_vectors_fts", schema=project_name)
    op.drop_index("idx_vectors_collection_ids", schema=project_name)
    op.drop_index("idx_vectors_user_id", schema=project_name)
    op.drop_index("idx_vectors_document_id", schema=project_name)

    # Drop the new table
    op.drop_table(new_vector_table_name, schema=project_name)
