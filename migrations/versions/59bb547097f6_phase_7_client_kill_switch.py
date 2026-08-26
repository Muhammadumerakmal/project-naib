"""phase 7 client kill switch

Revision ID: 59bb547097f6
Revises: cae02d6df2e9
Create Date: 2026-08-26 23:03:13.172110

Judgment call: autogenerate also proposed dropping `agent_sessions` /
`agent_messages` again — the OpenAI Agents SDK's own tables, never
Alembic-managed. Stripped those ops, same as the last three migrations.
Also added server_default=false() so this is safe against existing
`clients` rows (a bare nullable=False ADD COLUMN would fail on non-empty
tables without one).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '59bb547097f6'
down_revision: Union[str, Sequence[str], None] = 'cae02d6df2e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'clients',
        sa.Column('kill_switch', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('clients', 'kill_switch')
