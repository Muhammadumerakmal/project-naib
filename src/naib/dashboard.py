"""Query/service functions behind the Phase 7 dashboard — kept independent
of FastAPI so they're directly unit-testable (naib.dashboard_api is the
thin HTTP wrapper). Design note from PLAN.md: this UI's job is
reassurance, not density — every function here answers one of 'what did
it do' or 'can I stop it.'
"""

import uuid
from collections import defaultdict

from sqlmodel import select

from naib.approvals import Decision, decide_approval
from naib.schemas.approval_summary import ApprovalSummary
from naib.schemas.client_metrics import ClientMetrics, MetricsPoint
from naib.store.db import get_sessionmaker
from naib.store.models import AgentEvent, Approval, Client, Escalation, FollowUp, Lead, Proposal

_PREVIEW_CHARS = 140


def _preview(text: str) -> str:
    return text if len(text) <= _PREVIEW_CHARS else text[:_PREVIEW_CHARS].rstrip() + "…"


async def get_client(client_id: uuid.UUID) -> Client | None:
    async with get_sessionmaker()() as session:
        return (await session.exec(select(Client).where(Client.id == client_id))).first()


async def set_kill_switch(client_id: uuid.UUID, *, enabled: bool) -> Client:
    async with get_sessionmaker()() as session:
        client = (await session.exec(select(Client).where(Client.id == client_id))).one()
        client.kill_switch = enabled
        session.add(client)
        await session.commit()
        await session.refresh(client)
        return client


async def list_approval_summaries(
    client_id: uuid.UUID, *, entity_type: str | None = None, pending_only: bool = True
) -> list[ApprovalSummary]:
    async with get_sessionmaker()() as session:
        leads = (await session.exec(select(Lead).where(Lead.client_id == client_id))).all()
        lead_ids = {lead.id for lead in leads}
        if not lead_ids:
            return []

        proposals = {
            p.id: p
            for p in (
                await session.exec(select(Proposal).where(Proposal.lead_id.in_(lead_ids)))  # type: ignore[attr-defined]
            ).all()
        }
        followups = {
            f.id: f
            for f in (
                await session.exec(
                    select(FollowUp).where(FollowUp.proposal_id.in_(proposals.keys()))  # type: ignore[attr-defined]
                )
            ).all()
        }
        followup_to_lead = {
            f.id: proposals[f.proposal_id].lead_id
            for f in followups.values()
            if f.proposal_id in proposals
        }

        statement = select(Approval).where(
            Approval.entity_id.in_([*proposals.keys(), *followups.keys()])  # type: ignore[attr-defined]
        )
        if pending_only:
            statement = statement.where(Approval.decided_at.is_(None))  # type: ignore[union-attr]
        approvals = (await session.exec(statement)).all()

    summaries: list[ApprovalSummary] = []
    for approval in approvals:
        if entity_type is not None and approval.entity_type != entity_type:
            continue

        if approval.entity_type == "proposal" and approval.entity_id in proposals:
            proposal = proposals[approval.entity_id]
            full_text = proposal.draft_md
            lead_id = proposal.lead_id
        elif approval.entity_type == "followup" and approval.entity_id in followups:
            followup = followups[approval.entity_id]
            full_text = followup.message_md
            lead_id = followup_to_lead.get(approval.entity_id, uuid.UUID(int=0))
        else:
            continue

        summaries.append(
            ApprovalSummary(
                id=approval.id,
                entity_type=approval.entity_type,
                entity_id=approval.entity_id,
                action=approval.action,
                lead_id=lead_id,
                requested_at=approval.requested_at,
                decided_at=approval.decided_at,
                decided_by=approval.decided_by,
                decision=approval.decision,
                preview=_preview(full_text),
                full_text=full_text,
            )
        )

    return sorted(summaries, key=lambda s: s.requested_at, reverse=True)


async def list_client_escalations(client_id: uuid.UUID) -> list[Escalation]:
    async with get_sessionmaker()() as session:
        leads = (await session.exec(select(Lead).where(Lead.client_id == client_id))).all()
        lead_ids = [lead.id for lead in leads]
        if not lead_ids:
            return []
        escalations = (
            await session.exec(select(Escalation).where(Escalation.lead_id.in_(lead_ids)))  # type: ignore[attr-defined]
        ).all()
        return sorted(escalations, key=lambda e: e.created_at, reverse=True)


async def reject_or_decide_approval(
    approval_id: uuid.UUID,
    *,
    decided_by: str,
    decision: Decision,
    edit_diff: str | None = None,
) -> None:
    """Thin passthrough for entity types that need no extra persistence
    beyond the ledger row itself (unlike proposals — see
    naib.agents.proposal_pipeline.decide_proposal_approval for that case)."""

    await decide_approval(
        approval_id, decided_by=decided_by, decision=decision, edit_diff=edit_diff
    )


async def get_client_metrics(client_id: uuid.UUID) -> ClientMetrics:
    async with get_sessionmaker()() as session:
        leads = (await session.exec(select(Lead).where(Lead.client_id == client_id))).all()
        lead_ids = {lead.id for lead in leads}

        proposals = (
            (await session.exec(select(Proposal).where(Proposal.lead_id.in_(lead_ids)))).all()  # type: ignore[attr-defined]
            if lead_ids
            else []
        )
        proposal_ids = [p.id for p in proposals]
        approvals = (
            (
                await session.exec(
                    select(Approval).where(
                        Approval.entity_type == "proposal",
                        Approval.entity_id.in_(proposal_ids),  # type: ignore[attr-defined]
                        Approval.decided_at.is_not(None),  # type: ignore[union-attr]
                    )
                )
            ).all()
            if proposal_ids
            else []
        )

        events = (
            (
                await session.exec(
                    select(AgentEvent).where(AgentEvent.lead_id.in_(lead_ids))  # type: ignore[union-attr]
                )
            ).all()
            if lead_ids
            else []
        )

        escalations = (
            (
                await session.exec(
                    select(Escalation).where(Escalation.lead_id.in_(lead_ids))  # type: ignore[attr-defined]
                )
            ).all()
            if lead_ids
            else []
        )

    edit_buckets: dict[str, list[bool]] = defaultdict(list)
    for approval in approvals:
        assert approval.decided_at is not None
        day = approval.decided_at.date().isoformat()
        edit_buckets[day].append(approval.decision == "edited")
    edit_rate_over_time = [
        MetricsPoint(date=day, value=sum(edits) / len(edits))
        for day, edits in sorted(edit_buckets.items())
    ]

    cost_by_lead: dict[uuid.UUID, float] = defaultdict(float)
    first_event_by_lead: dict[uuid.UUID, AgentEvent] = {}
    for event in events:
        if event.lead_id is None:
            continue
        cost_by_lead[event.lead_id] += event.cost_usd or 0.0
        existing = first_event_by_lead.get(event.lead_id)
        if existing is None or event.created_at < existing.created_at:
            first_event_by_lead[event.lead_id] = event

    cost_buckets: dict[str, list[float]] = defaultdict(list)
    for lead in leads:
        day = lead.created_at.date().isoformat()
        cost_buckets[day].append(cost_by_lead.get(lead.id, 0.0))
    cost_per_lead_over_time = [
        MetricsPoint(date=day, value=sum(costs) / len(costs))
        for day, costs in sorted(cost_buckets.items())
    ]

    response_times = []
    for lead in leads:
        first_event = first_event_by_lead.get(lead.id)
        if first_event is not None:
            response_times.append((first_event.created_at - lead.created_at).total_seconds())
    avg_response_time = sum(response_times) / len(response_times) if response_times else None

    injections_blocked = sum(
        1 for e in escalations if e.reason == "guardrail_tripwire:injection_scan"
    )

    return ClientMetrics(
        edit_rate_over_time=edit_rate_over_time,
        cost_per_lead_over_time=cost_per_lead_over_time,
        injections_blocked_total=injections_blocked,
        avg_time_to_first_response_seconds=avg_response_time,
    )
