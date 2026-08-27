"""Graduated autonomy status (PLAN.md Phase 8: 'per-client, per-action,
unlockable after clean-log thresholds'). Read-only: this module reports
whether an action has earned its bar, it never acts on that report. See
naib.schemas.autonomy_status.AutonomyStatus for why eligible=True changes
nothing about tool permissions today.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlmodel import select

from naib.schemas.autonomy_status import AutonomyStatus
from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Approval, FollowUp, Lead, Proposal

# Which entity type backs each approval-gated action — see
# CLAUDE.md rule 2 for the full needs_approval=True list. send_email,
# send_whatsapp, and write_crm have no entity/action wired up yet because
# nothing in this codebase sends anything yet (also rule 2); add them here
# the day a real tool starts requesting approval for them.
_ACTION_ENTITY_TYPES: dict[str, str] = {
    "commit_price": "proposal",
    "send_followup": "followup",
}


async def compute_autonomy_status(client_id: uuid.UUID, action: str) -> AutonomyStatus:
    if action not in _ACTION_ENTITY_TYPES:
        raise ValueError(
            f"Unknown autonomy action {action!r} — expected one of "
            f"{sorted(_ACTION_ENTITY_TYPES)}"
        )
    entity_type = _ACTION_ENTITY_TYPES[action]
    settings = get_settings()
    window_days = settings.autonomy_window_days
    now = datetime.now(UTC)

    async with get_sessionmaker()() as session:
        leads = (await session.exec(select(Lead).where(Lead.client_id == client_id))).all()
        lead_ids = {lead.id for lead in leads}

        entities: Sequence[Proposal] | Sequence[FollowUp]
        if entity_type == "proposal":
            entities = (
                (await session.exec(select(Proposal).where(Proposal.lead_id.in_(lead_ids)))).all()  # type: ignore[attr-defined]
                if lead_ids
                else []
            )
        else:
            proposal_ids = (
                (
                    await session.exec(
                        select(Proposal.id).where(Proposal.lead_id.in_(lead_ids))  # type: ignore[attr-defined]
                    )
                ).all()
                if lead_ids
                else []
            )
            entities = (
                (
                    await session.exec(
                        select(FollowUp).where(FollowUp.proposal_id.in_(proposal_ids))  # type: ignore[attr-defined]
                    )
                ).all()
                if proposal_ids
                else []
            )
        entity_ids = [e.id for e in entities]

        decided = (
            (
                await session.exec(
                    select(Approval).where(
                        Approval.entity_type == entity_type,
                        Approval.entity_id.in_(entity_ids),  # type: ignore[attr-defined]
                        Approval.decided_at.is_not(None),  # type: ignore[union-attr]
                    )
                )
            ).all()
            if entity_ids
            else []
        )

    if not decided:
        return AutonomyStatus(
            client_id=client_id,
            action=action,
            window_days=window_days,
            days_tracked=0.0,
            decided_count=0,
            approved_count=0,
            edited_count=0,
            rejected_count=0,
            edit_or_reject_rate=1.0,
            eligible=False,
            reason="no_decided_approvals_yet",
        )

    earliest = min(a.decided_at for a in decided if a.decided_at is not None)
    days_tracked = min(float(window_days), (now - earliest).total_seconds() / 86400)

    cutoff = now.timestamp() - window_days * 86400
    in_window = [
        a for a in decided if a.decided_at is not None and a.decided_at.timestamp() >= cutoff
    ]

    decided_count = len(in_window)
    approved_count = sum(1 for a in in_window if a.decision == "approved")
    edited_count = sum(1 for a in in_window if a.decision == "edited")
    rejected_count = sum(1 for a in in_window if a.decision == "rejected")
    edit_or_reject_rate = (edited_count + rejected_count) / decided_count if decided_count else 1.0

    eligible = (
        days_tracked >= window_days
        and decided_count > 0
        and edit_or_reject_rate <= settings.autonomy_max_edit_rate
    )
    if eligible:
        reason = f"clean for {window_days}+ days ({decided_count} decisions, 0 edits/rejects)"
    elif days_tracked < window_days:
        reason = f"only {days_tracked:.1f} of {window_days} days tracked"
    else:
        reason = f"edit/reject rate {edit_or_reject_rate:.0%} exceeds threshold"

    return AutonomyStatus(
        client_id=client_id,
        action=action,
        window_days=window_days,
        days_tracked=days_tracked,
        decided_count=decided_count,
        approved_count=approved_count,
        edited_count=edited_count,
        rejected_count=rejected_count,
        edit_or_reject_rate=edit_or_reject_rate,
        eligible=eligible,
        reason=reason,
    )


async def compute_all_autonomy_status(client_id: uuid.UUID) -> list[AutonomyStatus]:
    return [
        await compute_autonomy_status(client_id, action) for action in _ACTION_ENTITY_TYPES
    ]
