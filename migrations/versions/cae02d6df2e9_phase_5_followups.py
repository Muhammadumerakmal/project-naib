"""phase 5 followups

Revision ID: cae02d6df2e9
Revises: 5a2d006025a9
Create Date: 2026-08-26 22:29:20.916045

Judgment call: autogenerate also proposed dropping `agent_sessions` /
`agent_messages` again — the OpenAI Agents SDK's own tables, never
Alembic-managed. Stripped those ops, same as the last two migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'cae02d6df2e9'
down_revision: Union[str, Sequence[str], None] = '5a2d006025a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('followups',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proposal_id', sa.Uuid(), nullable=False),
    sa.Column('attempt_number', sa.Integer(), nullable=False),
    sa.Column('message_md', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['proposal_id'], ['proposals.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('followups')
