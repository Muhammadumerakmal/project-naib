import uuid

from naib.approvals import decide_approval, request_approval
from naib.dashboard import (
    get_client_metrics,
    list_approval_summaries,
    list_client_escalations,
    set_kill_switch,
)
from naib.events import record_event
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, FollowUp, Lead, Proposal


async def _make_client() -> Client:
    async with get_sessionmaker()() as session:
        client = Client(name="Dashboard Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)
    return client


async def _make_lead(client: Client) -> Lead:
    async with get_sessionmaker()() as session:
        lead = Lead(client_id=client.id, channel="email", raw_hash=str(uuid.uuid4()))
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
    return lead


async def test_set_kill_switch_toggles_and_persists() -> None:
    client = await _make_client()

    updated = await set_kill_switch(client.id, enabled=True)

    assert updated.kill_switch is True


async def test_list_approval_summaries_includes_a_pending_proposal() -> None:
    client = await _make_client()
    lead = await _make_lead(client)

    async with get_sessionmaker()() as session:
        proposal = Proposal(
            lead_id=lead.id,
            playbook_entry_id="placeholder-website-basic",
            price_band="PKR 0 - PKR 99,999",
            draft_md="Hi, here is our proposal for your website...",
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)

    await request_approval(entity_type="proposal", entity_id=proposal.id, action="commit_price")

    summaries = await list_approval_summaries(client.id)

    assert len(summaries) == 1
    assert summaries[0].entity_type == "proposal"
    assert summaries[0].lead_id == lead.id
    assert "Hi, here is our proposal" in summaries[0].preview


async def test_list_approval_summaries_pending_only_excludes_decided() -> None:
    client = await _make_client()
    lead = await _make_lead(client)

    async with get_sessionmaker()() as session:
        proposal = Proposal(
            lead_id=lead.id,
            playbook_entry_id="placeholder-website-basic",
            price_band="PKR 0 - PKR 99,999",
            draft_md="draft",
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)

    approval = await request_approval(
        entity_type="proposal", entity_id=proposal.id, action="commit_price"
    )
    await decide_approval(approval.id, decided_by="umer@example.com", decision="approved")

    summaries = await list_approval_summaries(client.id, pending_only=True)

    assert summaries == []

    all_summaries = await list_approval_summaries(client.id, pending_only=False)
    assert len(all_summaries) == 1


async def test_list_approval_summaries_includes_a_followup() -> None:
    client = await _make_client()
    lead = await _make_lead(client)

    async with get_sessionmaker()() as session:
        proposal = Proposal(
            lead_id=lead.id,
            playbook_entry_id="placeholder-website-basic",
            price_band="PKR 0 - PKR 99,999",
            draft_md="draft",
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)

        followup = FollowUp(
            proposal_id=proposal.id, attempt_number=1, message_md="Just checking in!"
        )
        session.add(followup)
        await session.commit()
        await session.refresh(followup)

    await request_approval(entity_type="followup", entity_id=followup.id, action="send_followup")

    summaries = await list_approval_summaries(client.id, entity_type="followup")

    assert len(summaries) == 1
    assert summaries[0].lead_id == lead.id
    assert summaries[0].full_text == "Just checking in!"


async def test_list_client_escalations_returns_newest_first() -> None:
    client = await _make_client()
    lead = await _make_lead(client)

    async with get_sessionmaker()() as session:
        session.add(Escalation(lead_id=lead.id, reason="reason_a", brief_md="a"))
        await session.commit()
        session.add(Escalation(lead_id=lead.id, reason="reason_b", brief_md="b"))
        await session.commit()

    escalations = await list_client_escalations(client.id)

    assert [e.reason for e in escalations] == ["reason_b", "reason_a"]


async def test_get_client_metrics_computes_edit_rate_and_injections_blocked() -> None:
    client = await _make_client()
    lead = await _make_lead(client)

    async with get_sessionmaker()() as session:
        proposal = Proposal(
            lead_id=lead.id,
            playbook_entry_id="placeholder-website-basic",
            price_band="PKR 0 - PKR 99,999",
            draft_md="draft",
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)

        session.add(
            Escalation(
                lead_id=lead.id, reason="guardrail_tripwire:injection_scan", brief_md="x"
            )
        )
        await session.commit()

    approval = await request_approval(
        entity_type="proposal", entity_id=proposal.id, action="commit_price"
    )
    await decide_approval(approval.id, decided_by="umer@example.com", decision="edited")

    await record_event(
        run_id=uuid.uuid4(),
        agent="IntakeAgent",
        event_type="run",
        lead_id=lead.id,
        outcome="success",
    )

    metrics = await get_client_metrics(client.id)

    assert metrics.injections_blocked_total == 1
    assert len(metrics.edit_rate_over_time) == 1
    assert metrics.edit_rate_over_time[0].value == 1.0
