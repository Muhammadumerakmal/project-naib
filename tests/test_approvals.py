"""Phase 1 gate test: fabricated lead -> approval request -> human decision
-> edit diff persisted."""

import uuid

import pytest

from naib.approvals import decide_approval, list_pending, request_approval
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead


async def test_round_trip_approval_persists_edit_diff() -> None:
    async with get_sessionmaker()() as session:
        client = Client(name="Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="email", raw_hash="deadbeef")
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    approval = await request_approval(
        entity_type="proposal", entity_id=lead.id, action="commit_price"
    )
    assert approval.decided_at is None
    assert approval.decision is None

    pending = await list_pending(entity_type="proposal")
    assert any(a.id == approval.id for a in pending)

    decided = await decide_approval(
        approval.id,
        decided_by="umer@example.com",
        decision="edited",
        edit_diff="- PKR 50,000\n+ PKR 45,000",
    )

    assert decided.decision == "edited"
    assert decided.decided_by == "umer@example.com"
    assert decided.edit_diff == "- PKR 50,000\n+ PKR 45,000"
    assert decided.decided_at is not None

    still_pending = await list_pending(entity_type="proposal")
    assert all(a.id != approval.id for a in still_pending)


async def test_decide_approval_raises_for_unknown_id() -> None:
    with pytest.raises(KeyError):
        await decide_approval(uuid.uuid4(), decided_by="umer@example.com", decision="approved")
