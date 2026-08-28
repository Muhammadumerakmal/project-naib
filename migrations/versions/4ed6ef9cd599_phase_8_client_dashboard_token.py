"""phase 8 client dashboard token

Revision ID: 4ed6ef9cd599
Revises: 59bb547097f6
Create Date: 2026-08-28 15:17:22.897870

Judgment call: a bare `ADD COLUMN ... NOT NULL` fails against any existing
`clients` rows, and there's no sensible single `server_default` for a
per-row random secret. So this adds the column nullable, backfills every
existing row with its own generated token in Python (not a SQL default --
each row needs a *different* value), then tightens to NOT NULL. Safe on an
empty table (the common case pre-Phase-9) and on a populated one.
"""

import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4ed6ef9cd599'
down_revision: Union[str, Sequence[str], None] = '59bb547097f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('clients', sa.Column('dashboard_token', sa.String(), nullable=True))

    conn = op.get_bind()
    client_ids = conn.execute(sa.text('SELECT id FROM clients')).scalars().all()
    for client_id in client_ids:
        conn.execute(
            sa.text('UPDATE clients SET dashboard_token = :token WHERE id = :id'),
            {'token': secrets.token_urlsafe(32), 'id': client_id},
        )

    op.alter_column('clients', 'dashboard_token', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('clients', 'dashboard_token')
