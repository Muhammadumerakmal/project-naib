import uuid

from pydantic import BaseModel


class AutonomyStatus(BaseModel):
    """Where one client's one action stands against the graduated-autonomy
    bar (PLAN.md: 'earned per-client, per-action, after 30 days of clean
    logs' -- CLAUDE.md rule 2, docs/DEPLOYABILITY.md's autonomy-tiers
    pricing shape). This is a read-only status report: computing `eligible`
    here never flips `needs_approval` on any tool. Nothing in this codebase
    currently wires an eligible=True status to skipping the approval queue
    -- that wiring is a deliberate non-goal until a client has actually
    earned it on real traffic."""

    client_id: uuid.UUID
    action: str
    window_days: int
    days_tracked: float
    decided_count: int
    approved_count: int
    edited_count: int
    rejected_count: int
    edit_or_reject_rate: float
    eligible: bool
    reason: str
