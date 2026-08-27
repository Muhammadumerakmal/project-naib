import uuid
from datetime import UTC, datetime, timedelta

import pytest

from naib.approvals import decide_approval, request_approval
from naib.autonomy import compute_autonomy_status
from naib.store.db import get_sessionmaker
from naib.store.models import Approval, Client, Lead, Proposal


async def _make_client_and_lead() -> tuple[Client, Lead]:
    async with get_sessionmaker()() as session:
        client = Client(name="Autonomy Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="email", raw_hash=str(uuid.uuid4()))
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
    return client, lead


async def _decided_proposal_approval(
    lead: Lead, *, decision: str, decided_at: datetime
) -> None:
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
    await decide_approval(approval.id, decided_by="umer@example.com", decision=decision)  # type: ignore[arg-type]

    # Backdate decided_at directly -- decide_approval always stamps "now",
    # and these tests need to simulate a real 30-day history.
    async with get_sessionmaker()() as session:
        row = await session.get(Approval, approval.id)
        assert row is not None
        row.decided_at = decided_at
        session.add(row)
        await session.commit()


async def test_compute_autonomy_status_rejects_unknown_action() -> None:
    with pytest.raises(ValueError, match="Unknown autonomy action"):
        await compute_autonomy_status(uuid.uuid4(), "send_email")


async def test_no_decided_approvals_is_not_eligible() -> None:
    client, _lead = await _make_client_and_lead()

    status = await compute_autonomy_status(client.id, "commit_price")

    assert status.eligible is False
    assert status.reason == "no_decided_approvals_yet"
    assert status.decided_count == 0


async def test_not_enough_days_tracked_is_not_eligible() -> None:
    client, lead = await _make_client_and_lead()
    await _decided_proposal_approval(
        lead, decision="approved", decided_at=datetime.now(UTC) - timedelta(days=2)
    )

    status = await compute_autonomy_status(client.id, "commit_price")

    assert status.eligible is False
    assert status.days_tracked < status.window_days


async def test_clean_thirty_day_history_is_eligible() -> None:
    client, lead = await _make_client_and_lead()
    now = datetime.now(UTC)
    for days_ago in (35, 20, 5):
        await _decided_proposal_approval(
            lead, decision="approved", decided_at=now - timedelta(days=days_ago)
        )

    status = await compute_autonomy_status(client.id, "commit_price")

    assert status.eligible is True
    assert status.edit_or_reject_rate == 0.0
    # Only the two decisions inside the 30-day window count toward
    # decided_count -- the one 35 days ago only establishes days_tracked.
    assert status.decided_count == 2


async def test_a_single_edit_within_the_window_blocks_eligibility() -> None:
    client, lead = await _make_client_and_lead()
    now = datetime.now(UTC)
    await _decided_proposal_approval(
        lead, decision="approved", decided_at=now - timedelta(days=35)
    )
    await _decided_proposal_approval(
        lead, decision="edited", decided_at=now - timedelta(days=3)
    )

    status = await compute_autonomy_status(client.id, "commit_price")

    assert status.eligible is False
    assert status.edited_count == 1
    assert "exceeds threshold" in status.reason
