"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
Schema: %(schema)s
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}

def upgrade() -> None:
    # Get the schema name
    schema = op.get_context().get_context_kwargs.get('version_table_schema')

    """
    ### Schema-aware migration
    All table operations should include the schema name, for example:

    op.create_tables(
        'my_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        schema=schema
    )

    op.create_index(
        'idx_my_table_name',
        'my_table',
        ['name'],
        schema=schema
    )
    """
    ${upgrades if upgrades else "pass"}

def downgrade() -> None:
    # Get the schema name
    schema = op.get_context().get_context_kwargs.get('version_table_schema')

    """
    ### Schema-aware downgrade
    Remember to include schema in all operations, for example:

    op.drop_table('my_table', schema=schema)
    """
    ${downgrades if downgrades else "pass"}
