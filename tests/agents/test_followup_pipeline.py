import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from agents.testing import ScriptedModel, assistant_message
from sqlmodel import select

from naib.agents import followup_pipeline as followup_pipeline_module
from naib.agents.followup import build_followup_agent
from naib.agents.followup_pipeline import find_eligible_followups, run_followup_pipeline
from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, FollowUp, Lead, Proposal


def _wire_scripted_followup_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _build() -> object:
        agent = build_followup_agent()
        agent.model = ScriptedModel(
            [
                [
                    assistant_message(
                        json.dumps(
                            {
                                "message_md": "Hi, just checking in — any questions on the "
                                "proposal? Best, Naib",
                                "confidence": 0.7,
                                "reasons": ["Brief nudge"],
                            }
                        )
                    )
                ]
            ]
        )
        return agent

    monkeypatch.setattr(followup_pipeline_module, "build_followup_agent", _build)


async def _make_approved_proposal(*, approved_days_ago: int) -> Proposal:
    async with get_sessionmaker()() as session:
        client = Client(name="Followup Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="email", raw_hash=str(uuid.uuid4()))
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

        proposal = Proposal(
            lead_id=lead.id,
            playbook_entry_id="placeholder-website-basic",
            price_band="PKR 0 - PKR 99,999",
            draft_md="Hi, here is our proposal...",
            approved_by="umer@example.com",
            approved_at=datetime.now(UTC) - timedelta(days=approved_days_ago),
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)
        return proposal


async def test_run_followup_pipeline_persists_first_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_scripted_followup_agent(monkeypatch)
    proposal = await _make_approved_proposal(approved_days_ago=5)

    followup = await run_followup_pipeline(proposal_id=proposal.id)

    assert followup.attempt_number == 1
    assert followup.proposal_id == proposal.id


async def test_run_followup_pipeline_raises_once_attempts_are_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_scripted_followup_agent(monkeypatch)
    proposal = await _make_approved_proposal(approved_days_ago=30)
    max_attempts = get_settings().max_followup_attempts

    async with get_sessionmaker()() as session:
        for n in range(1, max_attempts + 1):
            session.add(
                FollowUp(proposal_id=proposal.id, attempt_number=n, message_md=f"attempt {n}")
            )
        await session.commit()

    with pytest.raises(ValueError, match="exhausted"):
        await run_followup_pipeline(proposal_id=proposal.id)


async def test_final_attempt_writes_an_exhaustion_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_scripted_followup_agent(monkeypatch)
    proposal = await _make_approved_proposal(approved_days_ago=30)
    max_attempts = get_settings().max_followup_attempts

    async with get_sessionmaker()() as session:
        for n in range(1, max_attempts):
            session.add(
                FollowUp(proposal_id=proposal.id, attempt_number=n, message_md=f"attempt {n}")
            )
        await session.commit()

    followup = await run_followup_pipeline(proposal_id=proposal.id)
    assert followup.attempt_number == max_attempts

    async with get_sessionmaker()() as session:
        lead = (
            await session.exec(select(Proposal).where(Proposal.id == proposal.id))
        ).one()
        escalations = (
            await session.exec(select(Escalation).where(Escalation.lead_id == lead.lead_id))
        ).all()
    assert any(e.reason == "followup_exhausted" for e in escalations)


async def test_find_eligible_followups_includes_a_proposal_due_for_contact() -> None:
    settings = get_settings()
    proposal = await _make_approved_proposal(approved_days_ago=settings.followup_interval_days + 1)

    eligible = await find_eligible_followups()

    assert proposal.id in eligible


async def test_find_eligible_followups_excludes_a_recently_approved_proposal() -> None:
    proposal = await _make_approved_proposal(approved_days_ago=0)

    eligible = await find_eligible_followups()

    assert proposal.id not in eligible


async def test_find_eligible_followups_excludes_an_exhausted_proposal() -> None:
    proposal = await _make_approved_proposal(approved_days_ago=30)
    max_attempts = get_settings().max_followup_attempts

    async with get_sessionmaker()() as session:
        for n in range(1, max_attempts + 1):
            session.add(
                FollowUp(proposal_id=proposal.id, attempt_number=n, message_md=f"attempt {n}")
            )
        await session.commit()

    eligible = await find_eligible_followups()

    assert proposal.id not in eligible
