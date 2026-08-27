"""`uv run python -m naib.cli replay <lead_id>` (documented in CLAUDE.md's
Commands section). Re-scores an existing lead's already-validated
`NormalizedLead` through QualifierAgent and re-routes it, without ever
touching raw untrusted text again -- the raw message was never stored in
the first place (naib.store.models.Lead only keeps `raw_hash`, by design;
see docs/ARCHITECTURE.md § Data model). That makes this the honest reading
of "replay": re-run the parts of the pipeline that operate on already-
cleared, schema-validated data, useful after an ICP or playbook change, or
to retry a lead that errored out mid-pipeline. It does NOT re-run
IntakeAgent -- there is nothing left for Intake to read.
"""

import uuid
from dataclasses import dataclass

from agents import Runner
from sqlmodel import select

from naib.agents.context import NaibContext
from naib.agents.enrichment import build_enrichment_agent
from naib.agents.qualifier import build_qualifier_agent
from naib.agents.retrieval import build_retrieval_agent
from naib.embeddings import OpenAIEmbedder
from naib.events import record_run, record_usage
from naib.icp import load_icp_config
from naib.schemas.normalized_lead import NormalizedLead
from naib.schemas.qualification_result import QualificationResult
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead, Qualification
from naib.worker import _route_qualified_lead  # deliberate reuse -- see module docstring


@dataclass
class ReplayResult:
    qualification: QualificationResult
    routing_status: str


async def replay_lead(lead_id: uuid.UUID) -> ReplayResult:
    async with get_sessionmaker()() as session:
        lead = (await session.exec(select(Lead).where(Lead.id == lead_id))).one()
        client = (await session.exec(select(Client).where(Client.id == lead.client_id))).one()

    if lead.normalized is None:
        raise ValueError(
            f"Lead {lead_id} has no normalized data on record -- it never made it past "
            "intake (or intake tripped a guardrail), so there is nothing to replay."
        )
    normalized_lead = NormalizedLead.model_validate(lead.normalized)

    enrichment_agent = build_enrichment_agent()
    retrieval_agent = build_retrieval_agent(OpenAIEmbedder())
    qualifier_agent = build_qualifier_agent(
        load_icp_config(client.icp_config), enrichment_agent, retrieval_agent
    )
    context = NaibContext(
        client=client,
        lead_id=lead_id,
        language=lead.language or normalized_lead.language,
        normalized_lead=normalized_lead,
    )

    async with record_run(agent="QualifierAgent", lead_id=lead_id) as record:
        result = await Runner.run(
            qualifier_agent,
            f"Normalized lead (replay from stored record):\n{normalized_lead.model_dump_json()}",
            context=context,
        )
        model = qualifier_agent.model if isinstance(qualifier_agent.model, str) else None
        record_usage(record, model=model, usage=result.context_wrapper.usage)

    qualification = result.final_output
    if not isinstance(qualification, QualificationResult):
        raise TypeError(
            f"QualifierAgent returned {type(qualification).__name__}, not a "
            "QualificationResult -- replay cannot route this."
        )

    async with get_sessionmaker()() as db_session:
        db_session.add(
            Qualification(
                lead_id=lead_id,
                score=qualification.score,
                band=qualification.band,
                reasons=qualification.reasons,
                disqualifiers=qualification.disqualifiers,
                model=model or "",
            )
        )
        await db_session.commit()

    status = await _route_qualified_lead(str(lead_id), client, qualification)
    return ReplayResult(qualification=qualification, routing_status=status)
