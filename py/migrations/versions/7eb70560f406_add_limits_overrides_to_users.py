"""add_limits_overrides_to_users.

Revision ID: 7eb70560f406
Revises: c45a9cf6a8a4
Create Date: 2025-01-03 20:27:16.139511
"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "7eb70560f406"
down_revision: Union[str, None] = "c45a9cf6a8a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

project_name = os.getenv("R2R_PROJECT_NAME", "r2r_default")


def check_if_upgrade_needed():
    """Check if the upgrade has already been applied."""
    connection = op.get_bind()
    inspector = inspect(connection)

    # Check if users table exists
    if not inspector.has_table("users", schema=project_name):
        print(
            f"Migration not needed: '{project_name}.users' table doesn't exist"
        )
        return False

    users_columns = {
        col["name"]
        for col in inspector.get_columns("users", schema=project_name)
    }

    if "limits_overrides" in users_columns:
        print(
            "Migration not needed: users table already has limits_overrides column"
        )
        return False
    else:
        print("Migration needed: users table needs limits_overrides column")
        return True


def upgrade() -> None:
    if not check_if_upgrade_needed():
        return

    # Add the limits_overrides column as JSONB with default NULL
    op.add_column(
        "users",
        sa.Column("limits_overrides", sa.JSON(), nullable=True),
        schema=project_name,
    )


def downgrade() -> None:
    # Remove the limits_overrides column
    op.drop_column("users", "limits_overrides", schema=project_name)
