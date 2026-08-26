import json

import pytest
from agents.testing import ScriptedModel, assistant_message
from sqlmodel import select

from naib.agents import escalation_pipeline as escalation_pipeline_module
from naib.agents.escalation import build_escalation_agent
from naib.agents.escalation_pipeline import run_escalation_pipeline
from naib.schemas.normalized_lead import NormalizedLead
from naib.schemas.qualification_result import QualificationResult
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, Lead


def _wire_scripted_escalation_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _build() -> object:
        agent = build_escalation_agent()
        agent.model = ScriptedModel(
            [
                [
                    assistant_message(
                        json.dumps(
                            {
                                "reason": "confidence_below_threshold:0.30",
                                "summary": "Vague inquiry, no clear service or budget signal.",
                                "conclusion": "Score 0.3, band low, confidence 0.3.",
                                "why_stopped": "Confidence 0.30 is below the 0.60 threshold.",
                                "recommendation": "Reply personally to clarify scope.",
                                "confidence": 0.3,
                                "reasons": ["Low confidence, vague request"],
                            }
                        )
                    )
                ]
            ]
        )
        return agent

    monkeypatch.setattr(escalation_pipeline_module, "build_escalation_agent", _build)


async def test_run_escalation_pipeline_persists_a_rendered_brief(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_scripted_escalation_agent(monkeypatch)

    async with get_sessionmaker()() as session:
        client = Client(name="Escalation Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="email", raw_hash="escalation-test")
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    normalized_lead = NormalizedLead(
        channel="email",
        message_summary="Vague inquiry about services.",
        language="en",
        raw_hash="escalation-test",
        confidence=0.3,
        reasons=["Vague request"],
    )
    qualification = QualificationResult(
        qualified=False,
        score=0.3,
        band="low",
        disqualifiers=[],
        should_escalate=True,
        confidence=0.3,
        reasons=["Low confidence"],
    )

    escalation = await run_escalation_pipeline(
        lead_id=lead.id,
        client=client,
        normalized_lead=normalized_lead,
        qualification=qualification,
        reason="confidence_below_threshold:0.30",
    )

    assert escalation.reason == "confidence_below_threshold:0.30"
    assert "Vague inquiry, no clear service or budget signal." in escalation.brief_md
    assert "Reply personally to clarify scope." in escalation.brief_md

    async with get_sessionmaker()() as session:
        rows = (
            await session.exec(select(Escalation).where(Escalation.lead_id == lead.id))
        ).all()
    assert len(rows) == 1
