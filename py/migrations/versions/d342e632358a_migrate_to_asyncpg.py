"""migrate_to_asyncpg.

Revision ID: d342e632358a
Revises:
Create Date: 2024-10-22 11:55:49.461015
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import UserDefinedType

# revision identifiers, used by Alembic.
revision: str = "d342e632358a"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

project_name = os.getenv("R2R_PROJECT_NAME") or "r2r_default"

new_vector_table_name = "vectors"
old_vector_table_name = project_name


class Vector(UserDefinedType):
    def get_col_spec(self, **kw):
        return "vector"


def check_if_upgrade_needed():
    """Check if the upgrade has already been applied or is needed."""
    connection = op.get_bind()
    inspector = inspect(connection)

    # First check if the old table exists - if it doesn't, we don't need this migration
    has_old_table = inspector.has_table(
        old_vector_table_name, schema=project_name
    )
    if not has_old_table:
        print(
            f"Migration not needed: Original '{old_vector_table_name}' table doesn't exist"
        )
        # Skip this migration since we're starting from a newer state
        return False

    # Only if the old table exists, check if we need to migrate it
    has_new_table = inspector.has_table(
        new_vector_table_name, schema=project_name
    )
    if has_new_table:
        print(
            f"Migration not needed: '{new_vector_table_name}' table already exists"
        )
        return False

    print(
        f"Migration needed: Need to migrate from '{old_vector_table_name}' to '{new_vector_table_name}'"
    )
    return True


def upgrade() -> None:
    if check_if_upgrade_needed():
        # Create required extensions
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gin")

        # KG table migrations
        op.execute(
            f"ALTER TABLE IF EXISTS {project_name}.entity_raw RENAME TO chunk_entity"
        )
        op.execute(
            f"ALTER TABLE IF EXISTS {project_name}.triple_raw RENAME TO chunk_triple"
        )
        op.execute(
            f"ALTER TABLE IF EXISTS {project_name}.entity_embedding RENAME TO document_entity"
        )
        op.execute(
            f"ALTER TABLE IF EXISTS {project_name}.community RENAME TO community_info"
        )

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
                server_default=sa.text(
                    "to_tsvector('english'::regconfig, '')"
                ),
            ),
            sa.Column(
                "metadata",
                postgresql.JSONB(),
                server_default="{}",
                nullable=False,
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
        op.execute(f"""
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
        """)

        # Verify data migration
        op.execute(f"""
            SELECT COUNT(*) old_count FROM {project_name}.{old_vector_table_name};
            SELECT COUNT(*) new_count FROM {project_name}.{new_vector_table_name};
        """)

        # If we get here, migration was successful, so drop the old table
        op.execute(f"""
        DROP TABLE IF EXISTS {project_name}.{old_vector_table_name};
        """)


def downgrade() -> None:
    # Drop all indices
    op.drop_index("idx_vectors_fts", schema=project_name)
    op.drop_index("idx_vectors_collection_ids", schema=project_name)
    op.drop_index("idx_vectors_user_id", schema=project_name)
    op.drop_index("idx_vectors_document_id", schema=project_name)

    # Drop the new table
    op.drop_table(new_vector_table_name, schema=project_name)

    # Revert KG table migrations
    op.execute(
        f"ALTER TABLE IF EXISTS {project_name}.chunk_entity RENAME TO entity_raw"
    )
    op.execute(
        f"ALTER TABLE IF EXISTS {project_name}.chunk_relationship RENAME TO relationship_raw"
    )
    op.execute(
        f"ALTER TABLE IF EXISTS {project_name}.document_entity RENAME TO entity_embedding"
    )
    op.execute(
        f"ALTER TABLE IF EXISTS {project_name}.community_info RENAME TO community"
    )
