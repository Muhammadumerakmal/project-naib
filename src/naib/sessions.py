"""Postgres-backed Agents SDK session, keyed per lead thread. Never
in-memory in production — see CLAUDE.md 'Sessions are Postgres-backed and
keyed per lead thread.'

Judgment call: rather than hand-rolling conversation-item storage — a
genuinely tricky concurrency problem, see the SDK's own SQLAlchemySession
handling row locking and retry-on-race for pop_item — PostgresSession is a
thin lead-keyed wrapper around the SDK's own, already-tested
SQLAlchemySession. It manages its own tables (agent_sessions,
agent_messages by default) rather than the `sessions` table sketched in
docs/ARCHITECTURE.md's Phase-0-era data model, which this phase's migration
drops now that the SDK's actual session contract is known. create_tables=True
lets it self-heal against whatever session schema the installed SDK version
actually expects, instead of us hand-duplicating that schema in an Alembic
migration that could drift out of sync on an SDK upgrade.
"""

import uuid

from agents.extensions.memory import SQLAlchemySession

from naib.store.db import get_engine


class PostgresSession(SQLAlchemySession):
    """One conversation history per lead."""

    def __init__(self, lead_id: uuid.UUID) -> None:
        super().__init__(session_id=str(lead_id), engine=get_engine(), create_tables=True)
