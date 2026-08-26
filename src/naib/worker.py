"""arq worker: the API boundary CLAUDE.md means when it says 'catch
InputGuardrailTripwireTriggered at the API boundary and return a structured
refusal + an escalation event.' Webhook handlers only enqueue; this is where
a lead actually runs through the pipeline.
"""

import uuid
from typing import Any

from agents import InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered
from arq.connections import RedisSettings
from sqlmodel import select

from naib.agents.pipeline import run_intake_qualifier
from naib.agents.proposal_pipeline import run_proposal_pipeline
from naib.schemas.normalized_lead import NormalizedLead
from naib.schemas.qualification_result import QualificationResult
from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, Lead
from naib.voice.pipeline import run_voice_pipeline
from naib.voice.transcription import OpenAIWhisperTranscriber


async def _escalate_on_tripwire(
    lead_id: str, guardrail_name: str, *, stage: str
) -> str:
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


async def _maybe_draft_proposal(
    lead_id: str, client: Client, qualification: QualificationResult
) -> str:
    """Only qualified leads get a proposal drafted — see
    docs/ARCHITECTURE.md's job description."""

    if not qualification.qualified:
        return f"qualified:{qualification.qualified}"

    async with get_sessionmaker()() as session:
        lead = (await session.exec(select(Lead).where(Lead.id == uuid.UUID(lead_id)))).one()
    if lead.normalized is None:
        return f"qualified:{qualification.qualified},no_proposal:missing_normalized_lead"

    try:
        await run_proposal_pipeline(
            lead_id=uuid.UUID(lead_id),
            client=client,
            normalized_lead=NormalizedLead.model_validate(lead.normalized),
            qualification=qualification,
        )
    except OutputGuardrailTripwireTriggered as exc:
        guardrail_name = exc.guardrail_result.guardrail.get_name()
        return await _escalate_on_tripwire(lead_id, guardrail_name, stage="proposal drafting")

    return f"qualified:{qualification.qualified},proposal:drafted"


async def process_lead(
    ctx: dict[str, Any], lead_id: str, client_id: str, raw_text: str, channel: str
) -> str:
    """arq job: run one lead through Intake -> Qualifier, then (if
    qualified) ProposalAgent. Returns a short status string (arq stores job
    results); the durable record is always the Qualification/Proposal/
    Escalation row, not the return value."""

    async with get_sessionmaker()() as session:
        client = (
            await session.exec(select(Client).where(Client.id == uuid.UUID(client_id)))
        ).one()

    try:
        qualification = await run_intake_qualifier(
            lead_id=uuid.UUID(lead_id), client=client, raw_text=raw_text, channel=channel
        )
    except InputGuardrailTripwireTriggered as exc:
        guardrail_name = exc.guardrail_result.guardrail.get_name()
        return await _escalate_on_tripwire(lead_id, guardrail_name, stage="intake")

    return await _maybe_draft_proposal(lead_id, client, qualification)


async def process_voice_lead(
    ctx: dict[str, Any], lead_id: str, client_id: str, recording_url: str
) -> str:
    """arq job: transcribe a voicemail recording, then run it through the
    unmodified Intake -> Qualifier -> Proposal pipeline. See PLAN.md
    Phase 2.5."""

    async with get_sessionmaker()() as session:
        client = (
            await session.exec(select(Client).where(Client.id == uuid.UUID(client_id)))
        ).one()

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

    return await _maybe_draft_proposal(lead_id, client, qualification)


async def _startup(ctx: dict[str, Any]) -> None:
    return None


async def _shutdown(ctx: dict[str, Any]) -> None:
    return None


class WorkerSettings:
    functions = [process_lead, process_voice_lead]
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
