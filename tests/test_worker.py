from typing import Any

import pytest
from agents import OutputGuardrailResult, OutputGuardrailTripwireTriggered
from agents.guardrail import GuardrailFunctionOutput
from sqlmodel import select

from naib import worker as worker_module
from naib.schemas.qualification_result import QualificationResult
from naib.settings import get_settings
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


def _qualification(
    *, qualified: bool, should_escalate: bool = False, confidence: float = 0.85
) -> QualificationResult:
    return QualificationResult(
        qualified=qualified,
        score=0.8 if qualified else 0.2,
        band="high" if qualified else "low",
        disqualifiers=[],
        should_escalate=should_escalate,
        confidence=confidence,
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


def test_escalation_reason_none_for_a_clean_confident_qualification() -> None:
    assert worker_module._escalation_reason(_qualification(qualified=True)) is None


def test_escalation_reason_respects_the_qualifiers_own_flag() -> None:
    reason = worker_module._escalation_reason(
        _qualification(qualified=False, should_escalate=True)
    )
    assert reason == "qualifier_flagged"


def test_escalation_reason_deterministic_backstop_below_confidence_threshold() -> None:
    """CLAUDE.md rule 6: below threshold -> escalate, even if the model
    itself didn't set should_escalate."""

    below = get_settings().escalate_below - 0.01
    reason = worker_module._escalation_reason(
        _qualification(qualified=True, should_escalate=False, confidence=below)
    )
    assert reason is not None
    assert reason.startswith("confidence_below_threshold")


async def test_route_qualified_lead_skips_proposal_for_unqualified_leads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, lead = await _make_client_and_lead(
        "worker-unqualified", normalized=_NORMALIZED_LEAD_DICT
    )

    async def _boom(**kwargs: object) -> object:
        raise AssertionError("run_proposal_pipeline should not run for an unqualified lead")

    monkeypatch.setattr(worker_module, "run_proposal_pipeline", _boom)

    status = await worker_module._route_qualified_lead(
        str(lead.id), client, _qualification(qualified=False)
    )

    assert status == "qualified:False"


async def test_route_qualified_lead_drafts_a_proposal_for_a_qualified_lead(
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

    status = await worker_module._route_qualified_lead(
        str(lead.id), client, _qualification(qualified=True)
    )

    assert status == "qualified:True,proposal:drafted"
    assert called["lead_id"] == lead.id


async def test_route_qualified_lead_escalates_on_output_guardrail_tripwire(
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

    status = await worker_module._route_qualified_lead(
        str(lead.id), client, _qualification(qualified=True)
    )

    assert status == "escalated:price_floor"

    async with get_sessionmaker()() as session:
        escalations = (
            await session.exec(select(Escalation).where(Escalation.lead_id == lead.id))
        ).all()
    assert len(escalations) == 1
    assert "price_floor" in escalations[0].reason


async def test_route_qualified_lead_escalates_instead_of_drafting_when_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lead can be qualified=True and still need a human — existing
    client, legal language, signal conflicts. Escalation must win."""

    client, lead = await _make_client_and_lead(
        "worker-escalate-over-qualified", normalized=_NORMALIZED_LEAD_DICT
    )

    async def _boom_proposal(**kwargs: object) -> object:
        raise AssertionError("run_proposal_pipeline should not run when should_escalate is True")

    escalation_called: dict[str, Any] = {}

    async def _fake_run_escalation_pipeline(**kwargs: object) -> object:
        escalation_called.update(kwargs)
        return object()

    monkeypatch.setattr(worker_module, "run_proposal_pipeline", _boom_proposal)
    monkeypatch.setattr(worker_module, "run_escalation_pipeline", _fake_run_escalation_pipeline)

    status = await worker_module._route_qualified_lead(
        str(lead.id), client, _qualification(qualified=True, should_escalate=True)
    )

    assert status == "escalated:qualifier_flagged"
    assert escalation_called["lead_id"] == lead.id
    assert escalation_called["reason"] == "qualifier_flagged"


async def _make_client_with_kill_switch(*, enabled: bool) -> Client:
    async with get_sessionmaker()() as session:
        client = Client(
            name="Kill Switch Test Agency",
            plan="pilot",
            playbook_version="v0",
            kill_switch=enabled,
        )
        session.add(client)
        await session.commit()
        await session.refresh(client)
    return client


async def test_process_lead_halts_when_kill_switch_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = await _make_client_with_kill_switch(enabled=True)

    async with get_sessionmaker()() as session:
        lead = Lead(client_id=client.id, channel="email", raw_hash="kill-switch-test")
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    async def _boom(**kwargs: object) -> object:
        raise AssertionError("run_intake_qualifier should not run while kill_switch is active")

    monkeypatch.setattr(worker_module, "run_intake_qualifier", _boom)

    status = await worker_module.process_lead({}, str(lead.id), str(client.id), "hi", "email")

    assert status == "halted:kill_switch"


async def test_process_lead_proceeds_when_kill_switch_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = await _make_client_with_kill_switch(enabled=False)

    async with get_sessionmaker()() as session:
        lead = Lead(client_id=client.id, channel="email", raw_hash="kill-switch-off-test")
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    called = {"ran": False}

    async def _fake_run_intake_qualifier(**kwargs: object) -> QualificationResult:
        called["ran"] = True
        return _qualification(qualified=False)

    monkeypatch.setattr(worker_module, "run_intake_qualifier", _fake_run_intake_qualifier)

    status = await worker_module.process_lead({}, str(lead.id), str(client.id), "hi", "email")

    assert called["ran"] is True
    assert status.startswith("qualified:False")
