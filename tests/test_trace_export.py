import uuid

from naib.events import record_event, record_run
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, Lead, Qualification
from naib.trace_export import export_signed_trace, verify_trace


async def _make_lead_with_history() -> uuid.UUID:
    async with get_sessionmaker()() as session:
        client = Client(name="Trace Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="email", raw_hash=str(uuid.uuid4()))
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

        session.add(
            Qualification(
                lead_id=lead.id, score=0.8, band="high", reasons=["x"], disqualifiers=[], model="m"
            )
        )
        session.add(Escalation(lead_id=lead.id, reason="test_reason", brief_md="brief"))
        await session.commit()

    async with record_run(agent="IntakeAgent", lead_id=lead.id) as record:
        record.model = "gpt-4.1-mini"
        record.tokens_in = 10
        record.tokens_out = 5
        record.cost_usd = 0.001

    await record_event(
        run_id=uuid.uuid4(),
        agent="IntakeAgent",
        event_type="guardrail",
        lead_id=lead.id,
        guardrail="injection_scan",
        outcome="clean",
    )

    return lead.id


async def test_export_signed_trace_includes_all_related_records() -> None:
    lead_id = await _make_lead_with_history()

    bundle = await export_signed_trace(lead_id)

    assert bundle["trace"]["lead_id"] == str(lead_id)
    assert len(bundle["trace"]["qualifications"]) == 1
    assert len(bundle["trace"]["escalations"]) == 1
    assert len(bundle["trace"]["events"]) == 2
    assert bundle["algorithm"] == "HMAC-SHA256"


async def test_verify_trace_accepts_an_unmodified_bundle() -> None:
    lead_id = await _make_lead_with_history()
    bundle = await export_signed_trace(lead_id)

    assert verify_trace(bundle) is True


async def test_verify_trace_rejects_a_tampered_bundle() -> None:
    lead_id = await _make_lead_with_history()
    bundle = await export_signed_trace(lead_id)

    bundle["trace"]["status"] = "qualified"  # tamper after signing

    assert verify_trace(bundle) is False
