"""phase 3 enrichment cache and proposal chunks

Revision ID: 5a2d006025a9
Revises: 5f39aa021dea
Create Date: 2026-08-26 21:40:11.418971

Judgment call: autogenerate also proposed dropping `agent_sessions` /
`agent_messages` — those are the OpenAI Agents SDK's own tables
(`naib.sessions.PostgresSession`, `create_tables=True`), never
Alembic-managed, so they always show up as "removed" against our
SQLModel.metadata. Stripped those ops, same as the Phase 1 `sessions`
migration had to work around.
"""
from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '5a2d006025a9'
down_revision: Union[str, Sequence[str], None] = '5f39aa021dea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.create_table('enrichment_cache',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('cache_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_enrichment_cache_cache_key'), 'enrichment_cache', ['cache_key'], unique=True)
    op.create_table('proposal_chunks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('proposal_label', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('scope_section', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('chunk_text', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True),
    sa.Column('is_synthetic', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('proposal_chunks')
    op.drop_index(op.f('ix_enrichment_cache_cache_key'), table_name='enrichment_cache')
    op.drop_table('enrichment_cache')
