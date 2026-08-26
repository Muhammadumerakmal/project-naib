"""Monthly client-facing report generator (docs/EVALS.md: 'This report is
the renewal conversation. Build the generator in Phase 6, not later.').
Leads processed/qualified/escalated, edit rate, injection attempts
blocked, cost vs. the human hour it displaced, every escalation with its
reason.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import select

from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import AgentEvent, Approval, Escalation, Lead, Proposal


@dataclass
class EscalationSummary:
    lead_id: uuid.UUID
    reason: str
    created_at: datetime


@dataclass
class MonthlyReport:
    client_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    leads_processed: int
    leads_qualified: int
    leads_not_qualified: int
    escalations: list[EscalationSummary]
    injection_attempts_blocked: int
    proposals_decided: int
    proposals_edited: int
    total_cost_usd: float
    escalation_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def edit_rate(self) -> float:
        return self.proposals_edited / self.proposals_decided if self.proposals_decided else 0.0

    @property
    def estimated_human_hours_displaced(self) -> float:
        settings = get_settings()
        return self.leads_processed * settings.human_minutes_per_lead_baseline / 60

    @property
    def estimated_human_cost_displaced_usd(self) -> float:
        settings = get_settings()
        return self.estimated_human_hours_displaced * settings.human_hourly_cost_usd


async def generate_monthly_report(
    client_id: uuid.UUID, *, period_start: datetime, period_end: datetime
) -> MonthlyReport:
    async with get_sessionmaker()() as session:
        leads = (
            await session.exec(
                select(Lead).where(
                    Lead.client_id == client_id,
                    Lead.created_at >= period_start,
                    Lead.created_at < period_end,
                )
            )
        ).all()
        lead_ids = [lead.id for lead in leads]

        escalations = (
            (
                await session.exec(
                    select(Escalation).where(Escalation.lead_id.in_(lead_ids))  # type: ignore[attr-defined]
                )
            ).all()
            if lead_ids
            else []
        )

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

    escalation_reasons: dict[str, int] = {}
    for esc in escalations:
        escalation_reasons[esc.reason] = escalation_reasons.get(esc.reason, 0) + 1

    return MonthlyReport(
        client_id=client_id,
        period_start=period_start,
        period_end=period_end,
        leads_processed=len(leads),
        leads_qualified=sum(1 for lead_row in leads if lead_row.status == "qualified"),
        leads_not_qualified=sum(1 for lead_row in leads if lead_row.status == "not_qualified"),
        escalations=[
            EscalationSummary(lead_id=e.lead_id, reason=e.reason, created_at=e.created_at)
            for e in escalations
        ],
        escalation_reasons=escalation_reasons,
        injection_attempts_blocked=escalation_reasons.get("guardrail_tripwire:injection_scan", 0),
        proposals_decided=len(approvals),
        proposals_edited=sum(1 for a in approvals if a.decision == "edited"),
        total_cost_usd=sum(e.cost_usd or 0.0 for e in events),
    )
