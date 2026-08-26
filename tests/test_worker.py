from typing import Any

import pytest
from agents import OutputGuardrailResult, OutputGuardrailTripwireTriggered
from agents.guardrail import GuardrailFunctionOutput
from sqlmodel import select

from naib import worker as worker_module
from naib.schemas.qualification_result import QualificationResult
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, Lead

_NORMALIZED_LEAD_DICT: dict[str, Any] = {
    "channel": "email",
    "contact_name": "Ali",
    "contact_email": "ali@example.com",
    "contact_phone": None,
    "company_name": None,
    "message_summary": "Wants a website.",
    "requested_service": "website",
    "budget_signal": None,
    "language": "en",
    "raw_hash": "x",
    "confidence": 0.9,
    "reasons": ["x"],
}


def _qualification(*, qualified: bool) -> QualificationResult:
    return QualificationResult(
        qualified=qualified,
        score=0.8 if qualified else 0.2,
        band="high" if qualified else "low",
        disqualifiers=[],
        should_escalate=False,
        confidence=0.85,
        reasons=["test"],
    )


async def _make_client_and_lead(
    raw_hash: str, *, normalized: dict[str, Any] | None = None
) -> tuple[Client, Lead]:
    async with get_sessionmaker()() as session:
        client = Client(name="Worker Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(
            client_id=client.id, channel="email", raw_hash=raw_hash, normalized=normalized
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
    return client, lead


async def test_maybe_draft_proposal_skips_unqualified_leads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, lead = await _make_client_and_lead("worker-unqualified")

    async def _boom(**kwargs: object) -> object:
        raise AssertionError("run_proposal_pipeline should not run for an unqualified lead")

    monkeypatch.setattr(worker_module, "run_proposal_pipeline", _boom)

    status = await worker_module._maybe_draft_proposal(
        str(lead.id), client, _qualification(qualified=False)
    )

    assert status == "qualified:False"


async def test_maybe_draft_proposal_drafts_for_a_qualified_lead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, lead = await _make_client_and_lead(
        "worker-qualified", normalized=_NORMALIZED_LEAD_DICT
    )

    called: dict[str, Any] = {}

    async def _fake_run_proposal_pipeline(**kwargs: object) -> object:
        called.update(kwargs)
        return object()

    monkeypatch.setattr(worker_module, "run_proposal_pipeline", _fake_run_proposal_pipeline)

    status = await worker_module._maybe_draft_proposal(
        str(lead.id), client, _qualification(qualified=True)
    )

    assert status == "qualified:True,proposal:drafted"
    assert called["lead_id"] == lead.id


async def test_maybe_draft_proposal_escalates_on_output_guardrail_tripwire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, lead = await _make_client_and_lead(
        "worker-tripwire", normalized=_NORMALIZED_LEAD_DICT
    )

    class _FakeGuardrail:
        def get_name(self) -> str:
            return "price_floor"

    async def _fake_run_proposal_pipeline(**kwargs: object) -> object:
        raise OutputGuardrailTripwireTriggered(
            OutputGuardrailResult(
                guardrail=_FakeGuardrail(),  # type: ignore[arg-type]
                agent_output=None,
                agent=None,  # type: ignore[arg-type]
                output=GuardrailFunctionOutput(output_info={}, tripwire_triggered=True),
            )
        )

    monkeypatch.setattr(worker_module, "run_proposal_pipeline", _fake_run_proposal_pipeline)

    status = await worker_module._maybe_draft_proposal(
        str(lead.id), client, _qualification(qualified=True)
    )

    assert status == "escalated:price_floor"

    async with get_sessionmaker()() as session:
        escalations = (
            await session.exec(select(Escalation).where(Escalation.lead_id == lead.id))
        ).all()
    assert len(escalations) == 1
    assert "price_floor" in escalations[0].reason
