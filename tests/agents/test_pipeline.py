"""End-to-end Intake -> Qualifier pipeline test against real Postgres, with
both agents' models swapped for `ScriptedModel` (docs/EVALS.md unit tier:
deterministic, zero cost). Proves persistence, not qualification accuracy —
accuracy is the golden-set eval's job (tests/evals/test_golden_set.py).
"""

import json

import pytest
from agents.testing import ScriptedModel, assistant_message, function_call
from sqlmodel import select

from naib.agents import pipeline as pipeline_module
from naib.agents.intake import build_intake_agent
from naib.agents.pipeline import run_intake_qualifier
from naib.agents.qualifier import build_qualifier_agent
from naib.icp import DEFAULT_ICP_CONFIG
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead, Qualification


def _wire_scripted_pipeline(monkeypatch: pytest.MonkeyPatch, *, normalized_lead_args: dict) -> None:
    def _build_qualifier(icp_config: object) -> object:
        agent = build_qualifier_agent(DEFAULT_ICP_CONFIG)
        agent.model = ScriptedModel(
            [
                [
                    assistant_message(
                        json.dumps(
                            {
                                "qualified": True,
                                "score": 0.75,
                                "band": "medium",
                                "disqualifiers": [],
                                "should_escalate": False,
                                "confidence": 0.8,
                                "reasons": ["Clear service request"],
                            }
                        )
                    )
                ]
            ]
        )
        return agent

    def _build_intake(qualifier_agent: object) -> object:
        agent = build_intake_agent(qualifier_agent)  # type: ignore[arg-type]
        handoff_tool_name = agent.handoffs[0].tool_name
        agent.model = ScriptedModel(
            [[function_call(handoff_tool_name, normalized_lead_args, call_id="call-1")]]
        )
        return agent

    monkeypatch.setattr(pipeline_module, "build_qualifier_agent", _build_qualifier)
    monkeypatch.setattr(pipeline_module, "build_intake_agent", _build_intake)


async def test_pipeline_persists_lead_and_qualification(monkeypatch: pytest.MonkeyPatch) -> None:
    async with get_sessionmaker()() as session:
        client = Client(name="Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="email", raw_hash="pipeline-test")
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    _wire_scripted_pipeline(
        monkeypatch,
        normalized_lead_args={
            "channel": "email",
            "contact_name": "Sara",
            "contact_email": "sara@example.com",
            "contact_phone": None,
            "company_name": "Sara Bakery",
            "message_summary": "Wants an online ordering page.",
            "requested_service": "website",
            "budget_signal": "PKR 60,000",
            "language": "en",
            "raw_hash": "pipeline-test",
            "confidence": 0.88,
            "reasons": ["Clear service request", "Budget stated"],
        },
    )

    result = await run_intake_qualifier(
        lead_id=lead.id,
        client=client,
        raw_text="Hi, I run a bakery and want an online ordering page. Budget ~60k PKR.",
        channel="email",
    )

    assert result.qualified is True

    async with get_sessionmaker()() as session:
        refreshed_lead = (await session.exec(select(Lead).where(Lead.id == lead.id))).one()
        qualifications = (
            await session.exec(select(Qualification).where(Qualification.lead_id == lead.id))
        ).all()

    assert refreshed_lead.status == "qualified"
    assert refreshed_lead.normalized is not None
    assert refreshed_lead.normalized["contact_email"] == "sara@example.com"
    assert len(qualifications) == 1
    assert qualifications[0].band == "medium"


async def test_pipeline_raises_type_error_if_handoff_chain_never_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A defensive check, not an expected path: if IntakeAgent produced a
    final message instead of handing off, we want a loud failure, not a
    silently wrong QualificationResult."""

    def _build_qualifier(icp_config: object) -> object:
        return build_qualifier_agent(DEFAULT_ICP_CONFIG)

    def _build_intake(qualifier_agent: object) -> object:
        agent = build_intake_agent(qualifier_agent)  # type: ignore[arg-type]
        agent.model = ScriptedModel([[assistant_message("I could not process this.")]])
        return agent

    monkeypatch.setattr(pipeline_module, "build_qualifier_agent", _build_qualifier)
    monkeypatch.setattr(pipeline_module, "build_intake_agent", _build_intake)

    async with get_sessionmaker()() as session:
        client = Client(name="Test Agency 2", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)
        lead = Lead(client_id=client.id, channel="email", raw_hash="incomplete-handoff")
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    with pytest.raises(TypeError, match="didn't complete"):
        await run_intake_qualifier(
            lead_id=lead.id, client=client, raw_text="garbled", channel="email"
        )
