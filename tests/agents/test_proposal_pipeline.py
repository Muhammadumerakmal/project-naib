import json
import uuid

import pytest
from agents.testing import ScriptedModel, assistant_message
from sqlmodel import select

from naib.agents import proposal_pipeline as proposal_pipeline_module
from naib.agents.proposal import build_proposal_agent
from naib.agents.proposal_pipeline import decide_proposal_approval, run_proposal_pipeline
from naib.approvals import list_pending
from naib.playbook import get_playbook_entry, render_price_band
from naib.schemas.normalized_lead import NormalizedLead
from naib.schemas.qualification_result import QualificationResult
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead, Proposal

_ENTRY = get_playbook_entry("placeholder-website-basic")
_GOOD_DRAFT_MD = (
    "Hi Ali,\n\nThanks for reaching out. We'd build a 5-page marketing site for your "
    f"business.\n\nInvestment: {render_price_band(_ENTRY)}.\n\nBest regards,\nNaib"
)


def _wire_scripted_proposal_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _build() -> object:
        agent = build_proposal_agent()
        agent.model = ScriptedModel(
            [
                [
                    assistant_message(
                        json.dumps(
                            {
                                "playbook_entry_id": _ENTRY.id,
                                "price_band": render_price_band(_ENTRY),
                                "scope_summary": "5-page marketing site",
                                "draft_md": _GOOD_DRAFT_MD,
                                "confidence": 0.85,
                                "reasons": ["Clear match"],
                            }
                        )
                    )
                ]
            ]
        )
        return agent

    monkeypatch.setattr(proposal_pipeline_module, "build_proposal_agent", _build)


async def _make_client_and_lead(raw_hash: str) -> tuple[Client, Lead]:
    async with get_sessionmaker()() as session:
        client = Client(name="Proposal Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="email", raw_hash=raw_hash)
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
    return client, lead


def _normalized_lead() -> NormalizedLead:
    return NormalizedLead(
        channel="email",
        contact_name="Ali",
        contact_email="ali@example.com",
        message_summary="Wants a 5-page website.",
        requested_service="website",
        language="en",
        raw_hash="proposal-test",
        confidence=0.9,
        reasons=["Clear service request"],
    )


def _qualification() -> QualificationResult:
    return QualificationResult(
        qualified=True,
        score=0.8,
        band="high",
        disqualifiers=[],
        should_escalate=False,
        confidence=0.85,
        reasons=["Clear service request"],
    )


async def test_run_proposal_pipeline_persists_a_pending_proposal_and_requests_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_scripted_proposal_agent(monkeypatch)
    client, lead = await _make_client_and_lead("proposal-pipeline-test")

    proposal = await run_proposal_pipeline(
        lead_id=lead.id,
        client=client,
        normalized_lead=_normalized_lead(),
        qualification=_qualification(),
    )

    assert proposal.playbook_entry_id == _ENTRY.id
    assert proposal.approved_by is None
    assert proposal.approved_at is None

    pending = await list_pending(entity_type="proposal")
    assert any(a.entity_id == proposal.id for a in pending)


async def test_decide_proposal_approval_approved_stamps_the_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_scripted_proposal_agent(monkeypatch)
    client, lead = await _make_client_and_lead("proposal-approve-test")

    proposal = await run_proposal_pipeline(
        lead_id=lead.id,
        client=client,
        normalized_lead=_normalized_lead(),
        qualification=_qualification(),
    )
    pending = await list_pending(entity_type="proposal")
    approval = next(a for a in pending if a.entity_id == proposal.id)

    decided = await decide_proposal_approval(
        approval.id, decided_by="umer@example.com", decision="approved"
    )

    assert decided.approved_by == "umer@example.com"
    assert decided.approved_at is not None
    assert decided.draft_md == _GOOD_DRAFT_MD


async def test_decide_proposal_approval_edited_updates_draft_and_bumps_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_scripted_proposal_agent(monkeypatch)
    client, lead = await _make_client_and_lead("proposal-edit-test")

    proposal = await run_proposal_pipeline(
        lead_id=lead.id,
        client=client,
        normalized_lead=_normalized_lead(),
        qualification=_qualification(),
    )
    pending = await list_pending(entity_type="proposal")
    approval = next(a for a in pending if a.entity_id == proposal.id)

    edited_md = _GOOD_DRAFT_MD.replace("5-page", "6-page")
    decided = await decide_proposal_approval(
        approval.id,
        decided_by="umer@example.com",
        decision="edited",
        edit_diff="- 5-page\n+ 6-page",
        edited_draft_md=edited_md,
    )

    assert decided.draft_md == edited_md
    assert decided.edited_diff == "- 5-page\n+ 6-page"
    assert decided.version == 2

    async with get_sessionmaker()() as session:
        refreshed = (
            await session.exec(select(Proposal).where(Proposal.id == proposal.id))
        ).one()
    assert refreshed.version == 2


async def test_decide_proposal_approval_requires_edited_draft_md_when_editing() -> None:
    with pytest.raises(ValueError, match="edited_draft_md is required"):
        await decide_proposal_approval(
            uuid.uuid4(), decided_by="umer@example.com", decision="edited"
        )
