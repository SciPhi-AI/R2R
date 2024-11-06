"""migrate_vector_table_optimizations

Revision ID: e342e632358b
Revises: d342e632358a
Create Date: 2024-10-23 14:55:49.461015

"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e342e632358b"
down_revision: str = "d342e632358a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

project_name = os.getenv("R2R_PROJECT_NAME") or "r2r_default"
vector_table = f"{project_name}.vectors"


def upgrade() -> None:
    # Enable required extensions (if not already enabled)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # Set optimal work memory settings
    op.execute("SET work_mem = '256MB';")
    op.execute("SET maintenance_work_mem = '1GB';")
    op.execute("SET effective_cache_size = '4GB';")

    # Drop old text search index if it exists
    op.execute(
        f"""
    DROP INDEX IF EXISTS {project_name}.idx_vectors_text;
    """
    )

    # Add new computed columns for text search
    op.execute(
        f"""
    ALTER TABLE {vector_table}
    ADD COLUMN IF NOT EXISTS text_search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', COALESCE(text, '')), 'B')
    ) STORED;

    ALTER TABLE {vector_table}
    ADD COLUMN IF NOT EXISTS metadata_search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', COALESCE(metadata::text, '')), 'A')
    ) STORED;
    """
    )

    # Create new optimized indices
    op.execute(
        f"""
    -- Text search indices
    CREATE INDEX IF NOT EXISTS idx_vectors_text_search
        ON {vector_table}
        USING GIN (text_search_vector);
    CREATE INDEX IF NOT EXISTS idx_vectors_metadata_search
        ON {vector_table}
        USING GIN (metadata_search_vector);

    -- Metadata index for fast JSON operations
    CREATE INDEX IF NOT EXISTS idx_vectors_metadata_json
        ON {vector_table}
        USING GIN (metadata jsonb_path_ops);
    """
    )

    # Create statistics for better query planning
    op.execute(
        f"""
    CREATE STATISTICS IF NOT EXISTS vectors_multi_stats (mcv)
        ON document_id, user_id
        FROM {vector_table};
    """
    )

    # Create materialized view for aggregated document text
    op.execute(
        f"""
    CREATE MATERIALIZED VIEW IF NOT EXISTS {project_name}.document_text_mv AS
    SELECT
        document_id,
        string_agg(text, ' ') as combined_text,
        setweight(to_tsvector('simple', string_agg(text, ' ')), 'B') as text_vector,
        setweight(to_tsvector('simple', string_agg(metadata::text, ' ')), 'A') as metadata_vector,
        COUNT(*) as chunk_count
    FROM {vector_table}
    GROUP BY document_id;

    CREATE UNIQUE INDEX IF NOT EXISTS idx_document_text_mv_id
        ON {project_name}.document_text_mv (document_id);
    CREATE INDEX IF NOT EXISTS idx_document_text_mv_text
        ON {project_name}.document_text_mv
        USING GIN (text_vector);
    CREATE INDEX IF NOT EXISTS idx_document_text_mv_metadata
        ON {project_name}.document_text_mv
        USING GIN (metadata_vector);
    """
    )

    # Analyze tables for better query planning
    op.execute(
        f"""
    ANALYZE {vector_table};
    ANALYZE {project_name}.document_text_mv;
    """
    )


def downgrade() -> None:
    # Drop new indices
    op.execute(
        f"""
    DROP INDEX IF EXISTS {project_name}.idx_vectors_text_search;
    DROP INDEX IF EXISTS {project_name}.idx_vectors_metadata_search;
    DROP INDEX IF EXISTS {project_name}.idx_vectors_metadata_json;
    """
    )

    # Drop statistics
    op.execute(
        f"""
    DROP STATISTICS IF EXISTS {project_name}.vectors_multi_stats;
    """
    )

    # Drop materialized view and its indices
    op.execute(
        f"""
    DROP MATERIALIZED VIEW IF EXISTS {project_name}.document_text_mv;
    """
    )

    # Drop computed columns
    op.execute(
        f"""
    ALTER TABLE {vector_table} DROP COLUMN IF EXISTS text_search_vector;
    ALTER TABLE {vector_table} DROP COLUMN IF EXISTS metadata_search_vector;
    """
    )

    # Recreate original text search index
    op.execute(
        f"""
    CREATE INDEX IF NOT EXISTS idx_vectors_text
    ON {vector_table}
    USING GIN (to_tsvector('english', text));
    """
    )
