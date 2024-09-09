"""add_ingestion_and_restructuring_status

Revision ID: 420467471060
Revises: 
Create Date: 2024-09-08 22:06:56.151700

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "420467471060"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns for ingestion and restructuring status
    op.add_column(
        "document_info",
        sa.Column(
            "ingestion_status",
            sa.Text(),
            server_default="pending",
            nullable=True,
        ),
    )
    op.add_column(
        "document_info",
        sa.Column(
            "restructuring_status",
            sa.Text(),
            server_default="pending",
            nullable=True,
        ),
    )

    # Copy data from 'status' to 'ingestion_status'
    op.execute("UPDATE document_info SET ingestion_status = status")

    # Drop old 'status' column
    op.drop_column("document_info", "status")

    # Change default value of ingestion_status
    op.alter_column(
        "document_info", "ingestion_status", server_default="pending"
    )


def downgrade() -> None:
    # Add back 'status' column
    op.add_column(
        "document_info",
        sa.Column(
            "status", sa.Text(), server_default="processing", nullable=True
        ),
    )

    # Copy data from 'ingestion_status' to 'status'
    op.execute("UPDATE document_info SET status = ingestion_status")

    # Drop new columns
    op.drop_column("document_info", "restructuring_status")
    op.drop_column("document_info", "ingestion_status")

    # Change default value of status back to 'processing'
    op.alter_column("document_info", "status", server_default="processing")
