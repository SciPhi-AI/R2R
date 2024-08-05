"""add_user_id_to_logs

Revision ID: 7423a09421e9
Revises:
Create Date: 2024-08-05 10:49:10.714423

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7423a09421e9"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Check and add user_id to logs table if it doesn't exist
    if "user_id" not in [col["name"] for col in inspector.get_columns("logs")]:
        op.add_column("logs", sa.Column("user_id", sa.String(), nullable=True))

    # Check and add user_id to log_info table if it doesn't exist
    if "user_id" not in [
        col["name"] for col in inspector.get_columns("log_info")
    ]:
        op.add_column(
            "log_info", sa.Column("user_id", sa.String(), nullable=True)
        )


def downgrade():
    # Remove user_id column from logs table if it exists
    with op.batch_alter_table("logs") as batch_op:
        batch_op.drop_column("user_id")

    # Remove user_id column from log_info table if it exists
    with op.batch_alter_table("log_info") as batch_op:
        batch_op.drop_column("user_id")
