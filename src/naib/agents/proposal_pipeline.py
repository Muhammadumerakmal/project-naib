"""Drafts a proposal, persists it as a pending `Proposal` row, and enqueues
a human approval. Raises `OutputGuardrailTripwireTriggered` unchanged if a
guardrail trips — same 'tripwires raise, caught at the boundary' pattern as
the text pipeline (CLAUDE.md rule, naib.worker). `decide_proposal_approval`
is the other half: what happens to the `Proposal` row once a human decides.
"""

import uuid

from agents import Runner
from sqlmodel import select

from naib.agents.context import NaibContext
from naib.agents.proposal import build_proposal_agent
from naib.approvals import Decision, decide_approval, request_approval
from naib.events import record_run
from naib.schemas.normalized_lead import NormalizedLead
from naib.schemas.proposal_draft import ProposalDraft
from naib.schemas.qualification_result import QualificationResult
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Proposal


async def run_proposal_pipeline(
    *,
    lead_id: uuid.UUID,
    client: Client,
    normalized_lead: NormalizedLead,
    qualification: QualificationResult,
) -> Proposal:
    agent = build_proposal_agent()
    context = NaibContext(
        client=client,
        lead_id=lead_id,
        language=normalized_lead.language,
        normalized_lead=normalized_lead,
    )
    lead_summary = (
        f"Company: {normalized_lead.company_name or 'unknown'}\n"
        f"Requested service: {normalized_lead.requested_service or 'unspecified'}\n"
        f"Budget signal: {normalized_lead.budget_signal or 'none stated'}\n"
        f"Message summary: {normalized_lead.message_summary}\n"
        f"Qualification score: {qualification.score} (band: {qualification.band})\n"
        f"Qualification reasons: {'; '.join(qualification.reasons)}\n"
    )

    async with record_run(agent="ProposalAgent", lead_id=lead_id) as record:
        result = await Runner.run(agent, lead_summary, context=context)
        record.model = agent.model if isinstance(agent.model, str) else None
        record.payload = {"final_agent": result.last_agent.name}

    draft = result.final_output
    if not isinstance(draft, ProposalDraft):
        raise TypeError(
            f"ProposalAgent ended without a ProposalDraft (got {type(draft).__name__})."
        )

    async with get_sessionmaker()() as session:
        proposal = Proposal(
            lead_id=lead_id,
            playbook_entry_id=draft.playbook_entry_id,
            price_band=draft.price_band,
            draft_md=draft.draft_md,
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)

    await request_approval(entity_type="proposal", entity_id=proposal.id, action="commit_price")

    return proposal


async def decide_proposal_approval(
    approval_id: uuid.UUID,
    *,
    decided_by: str,
    decision: Decision,
    edit_diff: str | None = None,
    edited_draft_md: str | None = None,
) -> Proposal:
    """Record the human decision on the trust ledger, then apply it to the
    linked `Proposal` row. `edited_draft_md` is required when `decision` is
    'edited' — the edit itself, not just its diff, is what gets committed."""

    if decision == "edited" and edited_draft_md is None:
        raise ValueError("edited_draft_md is required when decision is 'edited'")

    approval = await decide_approval(
        approval_id, decided_by=decided_by, decision=decision, edit_diff=edit_diff
    )

    async with get_sessionmaker()() as session:
        proposal = (
            await session.exec(select(Proposal).where(Proposal.id == approval.entity_id))
        ).one()

        if decision in ("approved", "edited"):
            proposal.approved_by = decided_by
            proposal.approved_at = approval.decided_at
        if decision == "edited":
            assert edited_draft_md is not None  # why: validated above; narrows for mypy
            proposal.draft_md = edited_draft_md
            proposal.edited_diff = edit_diff
            proposal.version += 1

        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)
        return proposal
