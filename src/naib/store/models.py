"""Postgres schema — see docs/ARCHITECTURE.md § Data model, which is the source
of truth for column lists. `agent_events` is append-only: never update, never
delete a row (enforced by convention here, by a hook at the shell level, and
should be enforced by DB grants in production).

Judgment call: `agent_events` and `escalations` gained a `created_at` beyond
what ARCHITECTURE.md lists, since an append-only event log needs an ordering
timestamp. Flagged in the Phase 0 handoff.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(UTC)


def _tz_datetime_column(*, nullable: bool) -> Column[datetime]:
    """All datetimes here are timezone-aware UTC (`_now`); the column must be
    too, or asyncpg rejects the mismatch against a naive `timestamp`."""

    return Column(DateTime(timezone=True), nullable=nullable)


class Client(SQLModel, table=True):
    __tablename__ = "clients"

    id: uuid.UUID = Field(default_factory=_uuid, primary_key=True)
    name: str
    plan: str
    icp_config: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB)
    )  # why: JSONB, shape is per-client config
    playbook_version: str
    price_floor: int = 0
    autonomy_level: str = "draft_only"


class Lead(SQLModel, table=True):
    __tablename__ = "leads"

    id: uuid.UUID = Field(default_factory=_uuid, primary_key=True)
    client_id: uuid.UUID = Field(foreign_key="clients.id")
    channel: str
    raw_hash: str
    normalized: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB)
    )  # why: JSONB, shape is the NormalizedLead schema (Phase 1)
    language: str | None = None
    status: str = "new"
    confidence: float | None = None
    created_at: datetime = Field(
        default_factory=_now, sa_column=_tz_datetime_column(nullable=False)
    )


class Qualification(SQLModel, table=True):
    __tablename__ = "qualifications"

    id: uuid.UUID = Field(default_factory=_uuid, primary_key=True)
    lead_id: uuid.UUID = Field(foreign_key="leads.id")
    score: float
    band: str
    reasons: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    disqualifiers: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    model: str


class Proposal(SQLModel, table=True):
    __tablename__ = "proposals"

    id: uuid.UUID = Field(default_factory=_uuid, primary_key=True)
    lead_id: uuid.UUID = Field(foreign_key="leads.id")
    playbook_entry_id: str
    price_band: str
    draft_md: str
    version: int = 1
    approved_by: str | None = None
    approved_at: datetime | None = Field(default=None, sa_column=_tz_datetime_column(nullable=True))
    edited_diff: str | None = None


class Approval(SQLModel, table=True):
    """The trust ledger. Every row where a human approved without editing is
    evidence the agent was right — the edit rate over time is the renewal
    argument. See docs/ARCHITECTURE.md."""

    __tablename__ = "approvals"

    id: uuid.UUID = Field(default_factory=_uuid, primary_key=True)
    entity_type: str
    entity_id: uuid.UUID
    action: str
    requested_at: datetime = Field(
        default_factory=_now, sa_column=_tz_datetime_column(nullable=False)
    )
    decided_at: datetime | None = Field(default=None, sa_column=_tz_datetime_column(nullable=True))
    decided_by: str | None = None
    decision: str | None = None
    edit_diff: str | None = None


class AgentEvent(SQLModel, table=True):
    """Append-only. Every run writes one of these per input hash, agent, tool
    call, guardrail outcome, model, tokens, cost, latency, and final decision
    with its reason string. See CLAUDE.md rule 3."""

    __tablename__ = "agent_events"

    id: uuid.UUID = Field(default_factory=_uuid, primary_key=True)
    run_id: uuid.UUID
    lead_id: uuid.UUID | None = None
    agent: str
    event_type: str
    tool: str | None = None
    guardrail: str | None = None
    outcome: str | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    payload: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB)
    )  # why: JSONB, shape varies per event_type
    created_at: datetime = Field(
        default_factory=_now, sa_column=_tz_datetime_column(nullable=False)
    )


class Escalation(SQLModel, table=True):
    __tablename__ = "escalations"

    id: uuid.UUID = Field(default_factory=_uuid, primary_key=True)
    lead_id: uuid.UUID = Field(foreign_key="leads.id")
    reason: str
    brief_md: str
    assigned_to: str | None = None
    resolved_at: datetime | None = Field(default=None, sa_column=_tz_datetime_column(nullable=True))
    created_at: datetime = Field(
        default_factory=_now, sa_column=_tz_datetime_column(nullable=False)
    )
