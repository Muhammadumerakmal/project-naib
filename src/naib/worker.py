"""arq worker: the API boundary CLAUDE.md means when it says 'catch
InputGuardrailTripwireTriggered at the API boundary and return a structured
refusal + an escalation event.' Webhook handlers only enqueue; this is where
a lead actually runs through the pipeline.
"""

import uuid
from typing import Any

from agents import InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered
from arq.connections import RedisSettings
from arq.cron import cron
from sqlmodel import select

from naib.agents.escalation_pipeline import run_escalation_pipeline
from naib.agents.followup_pipeline import find_eligible_followups, run_followup_pipeline
from naib.agents.pipeline import run_intake_qualifier
from naib.agents.proposal_pipeline import run_proposal_pipeline
from naib.schemas.normalized_lead import NormalizedLead
from naib.schemas.qualification_result import QualificationResult
from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, Lead, Proposal
from naib.voice.pipeline import run_voice_pipeline
from naib.voice.transcription import OpenAIWhisperTranscriber


def _kill_switch_active(client: Client) -> bool:
    """docs/ARCHITECTURE.md: 'halts all runs for a client instantly,
    mid-queue.' Checked at the top of every job entry point, before any
    agent runs — a queued job that hasn't started yet simply never starts.
    Phase 7 makes the dashboard button real; Phase 8 owns production
    testing of it."""

    return client.kill_switch


async def _escalate_on_tripwire(lead_id: str, guardrail_name: str, *, stage: str) -> str:
    async with get_sessionmaker()() as session:
        session.add(
            Escalation(
                lead_id=uuid.UUID(lead_id),
                reason=f"guardrail_tripwire:{guardrail_name}",
                brief_md=(
                    f"# Escalation — guardrail tripwire\n\n"
                    f"`{guardrail_name}` tripped during {stage}. A human needs to "
                    f"read the original message directly."
                ),
            )
        )
        await session.commit()
    return f"escalated:{guardrail_name}"


def _escalation_reason(qualification: QualificationResult) -> str | None:
    """Deterministic backstop on top of the qualifier's own judgment
    (docs/EVALS.md 'Deterministic first', CLAUDE.md rule 6: below threshold
    -> hand off to EscalationAgent). The qualifier's should_escalate can
    still fire for reasons this doesn't catch (hard disqualifiers, signal
    conflicts) — this only adds a confidence floor the pipeline enforces
    regardless of what the model claimed."""

    if qualification.should_escalate:
        return "qualifier_flagged"
    if qualification.confidence < get_settings().escalate_below:
        return f"confidence_below_threshold:{qualification.confidence:.2f}"
    return None


async def _route_qualified_lead(
    lead_id: str, client: Client, qualification: QualificationResult
) -> str:
    """Escalation takes priority over proposal drafting — a lead can be
    'qualified' and still need a human (existing client, legal language).
    See docs/ARCHITECTURE.md agent topology: Qualifier's terminal branch is
    Proposal *or* Escalation, never both."""

    async with get_sessionmaker()() as session:
        lead = (await session.exec(select(Lead).where(Lead.id == uuid.UUID(lead_id)))).one()
    if lead.normalized is None:
        return f"qualified:{qualification.qualified},no_action:missing_normalized_lead"
    normalized_lead = NormalizedLead.model_validate(lead.normalized)

    reason = _escalation_reason(qualification)
    if reason is not None:
        await run_escalation_pipeline(
            lead_id=uuid.UUID(lead_id),
            client=client,
            normalized_lead=normalized_lead,
            qualification=qualification,
            reason=reason,
        )
        return f"escalated:{reason}"

    if not qualification.qualified:
        return f"qualified:{qualification.qualified}"

    try:
        await run_proposal_pipeline(
            lead_id=uuid.UUID(lead_id),
            client=client,
            normalized_lead=normalized_lead,
            qualification=qualification,
        )
    except OutputGuardrailTripwireTriggered as exc:
        guardrail_name = exc.guardrail_result.guardrail.get_name()
        return await _escalate_on_tripwire(lead_id, guardrail_name, stage="proposal drafting")

    return f"qualified:{qualification.qualified},proposal:drafted"


async def process_lead(
    ctx: dict[str, Any], lead_id: str, client_id: str, raw_text: str, channel: str
) -> str:
    """arq job: run one lead through Intake -> Qualifier, then route to
    Proposal or Escalation. Returns a short status string (arq stores job
    results); the durable record is always the Qualification/Proposal/
    Escalation row, not the return value."""

    async with get_sessionmaker()() as session:
        client = (
            await session.exec(select(Client).where(Client.id == uuid.UUID(client_id)))
        ).one()

    if _kill_switch_active(client):
        return "halted:kill_switch"

    try:
        qualification = await run_intake_qualifier(
            lead_id=uuid.UUID(lead_id), client=client, raw_text=raw_text, channel=channel
        )
    except InputGuardrailTripwireTriggered as exc:
        guardrail_name = exc.guardrail_result.guardrail.get_name()
        return await _escalate_on_tripwire(lead_id, guardrail_name, stage="intake")

    return await _route_qualified_lead(lead_id, client, qualification)


async def process_voice_lead(
    ctx: dict[str, Any], lead_id: str, client_id: str, recording_url: str
) -> str:
    """arq job: transcribe a voicemail recording, then run it through the
    unmodified Intake -> Qualifier -> Proposal/Escalation pipeline. See
    PLAN.md Phase 2.5."""

    async with get_sessionmaker()() as session:
        client = (
            await session.exec(select(Client).where(Client.id == uuid.UUID(client_id)))
        ).one()

    if _kill_switch_active(client):
        return "halted:kill_switch"

    try:
        qualification = await run_voice_pipeline(
            lead_id=uuid.UUID(lead_id),
            client=client,
            recording_url=recording_url,
            transcriber=OpenAIWhisperTranscriber(),
        )
    except InputGuardrailTripwireTriggered as exc:
        guardrail_name = exc.guardrail_result.guardrail.get_name()
        return await _escalate_on_tripwire(lead_id, guardrail_name, stage="voice intake")

    return await _route_qualified_lead(lead_id, client, qualification)


async def process_followup(ctx: dict[str, Any], proposal_id: str) -> str:
    """arq job: compose one follow-up draft for an approved-but-unanswered
    proposal. Gated by naib.agents.followup_pipeline's exhaustion rules —
    this function does not decide eligibility, `scan_for_due_followups`
    (the cron job below) already did."""

    async with get_sessionmaker()() as session:
        proposal = (
            await session.exec(select(Proposal).where(Proposal.id == uuid.UUID(proposal_id)))
        ).one()
        lead = (await session.exec(select(Lead).where(Lead.id == proposal.lead_id))).one()
        client = (await session.exec(select(Client).where(Client.id == lead.client_id))).one()

    if _kill_switch_active(client):
        return "halted:kill_switch"

    followup = await run_followup_pipeline(proposal_id=uuid.UUID(proposal_id))
    return f"followup:{followup.attempt_number}"


async def scan_for_due_followups(ctx: dict[str, Any]) -> str:
    """Cron job: enqueue `process_followup` for every proposal whose
    follow-up cadence is due. See naib.agents.followup_pipeline for the
    interval/exhaustion rules (PLAN.md Phase 5: 'gated'). `ctx['redis']` is
    the same arq pool this worker already runs on — no second connection."""

    eligible = await find_eligible_followups()
    for proposal_id in eligible:
        await ctx["redis"].enqueue_job("process_followup", str(proposal_id))
    return f"enqueued:{len(eligible)}"


async def _startup(ctx: dict[str, Any]) -> None:
    return None


async def _shutdown(ctx: dict[str, Any]) -> None:
    return None


class WorkerSettings:
    functions = [process_lead, process_voice_lead, process_followup]
    cron_jobs = [cron(scan_for_due_followups, minute=0)]  # hourly, on the hour
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
