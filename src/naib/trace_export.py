"""Per-lead trace export: a signed JSON bundle a client can inspect
end-to-end — every event, guardrail outcome, cost, and decision for one
lead, in plain language terms plus the raw record. See PLAN.md Phase 6 and
CLAUDE.md rule 3 ('every decision is reconstructable... we answer with a
record, not a shrug').
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select

from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import (
    AgentEvent,
    Approval,
    Escalation,
    FollowUp,
    Lead,
    Proposal,
    Qualification,
)

ALGORITHM = "HMAC-SHA256"


async def build_lead_trace(lead_id: uuid.UUID) -> dict[str, Any]:
    async with get_sessionmaker()() as session:
        lead = (await session.exec(select(Lead).where(Lead.id == lead_id))).one()
        qualifications = (
            await session.exec(select(Qualification).where(Qualification.lead_id == lead_id))
        ).all()
        proposals = (
            await session.exec(select(Proposal).where(Proposal.lead_id == lead_id))
        ).all()
        escalations = (
            await session.exec(select(Escalation).where(Escalation.lead_id == lead_id))
        ).all()
        events = (
            await session.exec(
                select(AgentEvent)
                .where(AgentEvent.lead_id == lead_id)
                .order_by(AgentEvent.created_at)  # type: ignore[arg-type]
            )
        ).all()

        proposal_ids = [p.id for p in proposals]
        followups = (
            (
                await session.exec(
                    select(FollowUp).where(FollowUp.proposal_id.in_(proposal_ids))  # type: ignore[attr-defined]
                )
            ).all()
            if proposal_ids
            else []
        )

        approval_entity_ids = [lead_id, *proposal_ids, *(f.id for f in followups)]
        approvals = (
            await session.exec(
                select(Approval).where(Approval.entity_id.in_(approval_entity_ids))  # type: ignore[attr-defined]
            )
        ).all()

    return {
        "lead_id": str(lead_id),
        "client_id": str(lead.client_id),
        "channel": lead.channel,
        "status": lead.status,
        "language": lead.language,
        "confidence": lead.confidence,
        "created_at": lead.created_at.isoformat(),
        "qualifications": [
            {
                "score": q.score,
                "band": q.band,
                "reasons": q.reasons,
                "disqualifiers": q.disqualifiers,
                "model": q.model,
            }
            for q in qualifications
        ],
        "proposals": [
            {
                "id": str(p.id),
                "playbook_entry_id": p.playbook_entry_id,
                "price_band": p.price_band,
                "version": p.version,
                "approved_by": p.approved_by,
                "approved_at": p.approved_at.isoformat() if p.approved_at else None,
            }
            for p in proposals
        ],
        "escalations": [
            {"reason": e.reason, "created_at": e.created_at.isoformat()} for e in escalations
        ],
        "followups": [
            {"attempt_number": f.attempt_number, "created_at": f.created_at.isoformat()}
            for f in followups
        ],
        "approvals": [
            {
                "entity_type": a.entity_type,
                "action": a.action,
                "decision": a.decision,
                "decided_by": a.decided_by,
                "decided_at": a.decided_at.isoformat() if a.decided_at else None,
            }
            for a in approvals
        ],
        "events": [
            {
                "run_id": str(e.run_id),
                "agent": e.agent,
                "event_type": e.event_type,
                "tool": e.tool,
                "guardrail": e.guardrail,
                "outcome": e.outcome,
                "model": e.model,
                "tokens_in": e.tokens_in,
                "tokens_out": e.tokens_out,
                "cost_usd": e.cost_usd,
                "latency_ms": e.latency_ms,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


def sign_trace(trace: dict[str, Any]) -> str:
    secret = get_settings().trace_export_secret
    payload = json.dumps(trace, sort_keys=True, default=str).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


async def export_signed_trace(lead_id: uuid.UUID) -> dict[str, Any]:
    trace = await build_lead_trace(lead_id)
    return {
        "trace": trace,
        "signature": sign_trace(trace),
        "algorithm": ALGORITHM,
        "signed_at": datetime.now(UTC).isoformat(),
    }


def verify_trace(bundle: dict[str, Any]) -> bool:
    expected = sign_trace(bundle["trace"])
    return hmac.compare_digest(expected, bundle["signature"])
