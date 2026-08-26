"""Drafts an escalation brief and persists it as an `Escalation` row. Unlike
proposals, an escalation has no approve/reject/edit cycle of its own — the
brief *is* the hand-back to a human (docs/ARCHITECTURE.md: EscalationAgent
'writes a human handoff brief'), so there is nothing to queue in the
approvals ledger.
"""

import uuid

from agents import Runner

from naib.agents.context import NaibContext
from naib.agents.escalation import build_escalation_agent
from naib.events import record_run
from naib.schemas.escalation_brief import EscalationBrief
from naib.schemas.normalized_lead import NormalizedLead
from naib.schemas.qualification_result import QualificationResult
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation


def _render_brief_md(brief: EscalationBrief, *, reason: str) -> str:
    return (
        f"# Escalation — {reason}\n\n"
        f"**What came in:** {brief.summary}\n\n"
        f"**What the pipeline concluded:** {brief.conclusion}\n\n"
        f"**Why it stopped here:** {brief.why_stopped}\n\n"
        f"**Recommendation:** {brief.recommendation}\n\n"
        f"**Confidence:** {brief.confidence}\n\n"
        f"**Reasons:**\n" + "\n".join(f"- {r}" for r in brief.reasons)
    )


async def run_escalation_pipeline(
    *,
    lead_id: uuid.UUID,
    client: Client,
    normalized_lead: NormalizedLead,
    qualification: QualificationResult,
    reason: str,
) -> Escalation:
    agent = build_escalation_agent()
    context = NaibContext(
        client=client,
        lead_id=lead_id,
        language=normalized_lead.language,
        normalized_lead=normalized_lead,
    )
    lead_summary = (
        f"Escalation reason: {reason}\n"
        f"Company: {normalized_lead.company_name or 'unknown'}\n"
        f"Requested service: {normalized_lead.requested_service or 'unspecified'}\n"
        f"Message summary: {normalized_lead.message_summary}\n"
        f"Qualification: qualified={qualification.qualified}, score={qualification.score}, "
        f"band={qualification.band}, confidence={qualification.confidence}\n"
        f"Disqualifiers: {', '.join(qualification.disqualifiers) or 'none'}\n"
        f"Qualifier reasons: {'; '.join(qualification.reasons)}\n"
    )

    async with record_run(agent="EscalationAgent", lead_id=lead_id) as record:
        result = await Runner.run(agent, lead_summary, context=context)
        record.model = agent.model if isinstance(agent.model, str) else None

    brief = result.final_output
    if not isinstance(brief, EscalationBrief):
        raise TypeError(
            f"EscalationAgent ended without an EscalationBrief (got {type(brief).__name__})."
        )

    async with get_sessionmaker()() as session:
        escalation = Escalation(
            lead_id=lead_id, reason=reason, brief_md=_render_brief_md(brief, reason=reason)
        )
        session.add(escalation)
        await session.commit()
        await session.refresh(escalation)
        return escalation
