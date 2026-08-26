"""Orchestrates the Intake -> Qualifier pipeline end to end: preprocess the
raw inbound message (PII redaction, language detection, untrusted-text
wrapping), run the two agents through `Runner.run`, and persist the result.
Tripwires are NOT caught here — CLAUDE.md rule: 'Tripwires raise. Catch
InputGuardrailTripwireTriggered at the API boundary' — that boundary is the
arq worker (`naib.worker`), not this module.
"""

import uuid

from agents import Runner
from sqlmodel import select

from naib.agents.context import NaibContext
from naib.agents.enrichment import build_enrichment_agent
from naib.agents.intake import build_intake_agent
from naib.agents.qualifier import build_qualifier_agent
from naib.agents.retrieval import build_retrieval_agent
from naib.embeddings import OpenAIEmbedder
from naib.events import record_run, record_usage
from naib.guardrails.injection import wrap_untrusted
from naib.guardrails.language_route import detect_language
from naib.guardrails.pii import redact_pii
from naib.icp import load_icp_config
from naib.schemas.normalized_lead import NormalizedLead
from naib.schemas.qualification_result import QualificationResult
from naib.sessions import PostgresSession
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead, Qualification


async def run_intake_qualifier(
    *, lead_id: uuid.UUID, client: Client, raw_text: str, channel: str
) -> QualificationResult:
    """Preprocess, run the pipeline, persist Lead/Qualification rows, and
    return the QualificationResult. Raises InputGuardrailTripwireTriggered
    unchanged if a guardrail trips — the caller decides what that means."""

    redacted_text, _redacted_types = redact_pii(raw_text)
    language, _confidence = detect_language(redacted_text)
    wrapped = wrap_untrusted(redacted_text, source=channel)

    enrichment_agent = build_enrichment_agent()
    retrieval_agent = build_retrieval_agent(OpenAIEmbedder())
    qualifier_agent = build_qualifier_agent(
        load_icp_config(client.icp_config), enrichment_agent, retrieval_agent
    )
    intake_agent = build_intake_agent(qualifier_agent)
    context = NaibContext(client=client, lead_id=lead_id, language=language)
    session = PostgresSession(lead_id)

    async with record_run(agent="IntakeAgent", lead_id=lead_id) as record:
        result = await Runner.run(intake_agent, wrapped, context=context, session=session)
        model = intake_agent.model if isinstance(intake_agent.model, str) else None
        record_usage(record, model=model, usage=result.context_wrapper.usage)
        record.payload = {"final_agent": result.last_agent.name}

    qualification = result.final_output
    if not isinstance(qualification, QualificationResult):
        raise TypeError(
            f"Pipeline ended at {result.last_agent.name} without a QualificationResult "
            f"(got {type(qualification).__name__}) — the handoff chain didn't complete."
        )

    normalized_lead: NormalizedLead | None = context.normalized_lead
    async with get_sessionmaker()() as db_session:
        lead = (await db_session.exec(select(Lead).where(Lead.id == lead_id))).one()
        lead.language = language
        lead.confidence = qualification.confidence
        lead.status = "qualified" if qualification.qualified else "not_qualified"
        lead.normalized = normalized_lead.model_dump() if normalized_lead else None
        db_session.add(lead)

        db_session.add(
            Qualification(
                lead_id=lead_id,
                score=qualification.score,
                band=qualification.band,
                reasons=qualification.reasons,
                disqualifiers=qualification.disqualifiers,
                model=qualifier_agent.model if isinstance(qualifier_agent.model, str) else "",
            )
        )
        await db_session.commit()

    return qualification
