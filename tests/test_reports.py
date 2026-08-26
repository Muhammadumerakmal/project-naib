import uuid
from datetime import UTC, datetime, timedelta

from naib.approvals import decide_approval, request_approval
from naib.events import record_event
from naib.reports import generate_monthly_report
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, Lead, Proposal


async def test_generate_monthly_report_counts_leads_and_escalations() -> None:
    async with get_sessionmaker()() as session:
        client = Client(name="Report Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        qualified_lead = Lead(
            client_id=client.id, channel="email", raw_hash=str(uuid.uuid4()), status="qualified"
        )
        not_qualified_lead = Lead(
            client_id=client.id,
            channel="email",
            raw_hash=str(uuid.uuid4()),
            status="not_qualified",
        )
        session.add(qualified_lead)
        session.add(not_qualified_lead)
        await session.commit()
        await session.refresh(qualified_lead)
        await session.refresh(not_qualified_lead)

        session.add(
            Escalation(
                lead_id=not_qualified_lead.id,
                reason="guardrail_tripwire:injection_scan",
                brief_md="x",
            )
        )
        await session.commit()

        proposal = Proposal(
            lead_id=qualified_lead.id,
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
    await decide_approval(approval.id, decided_by="umer@example.com", decision="edited")

    await record_event(
        run_id=uuid.uuid4(),
        agent="IntakeAgent",
        event_type="run",
        lead_id=qualified_lead.id,
        outcome="success",
        payload={"cost_usd": 0.01},
    )

    now = datetime.now(UTC)
    report = await generate_monthly_report(
        client.id, period_start=now - timedelta(days=1), period_end=now + timedelta(days=1)
    )

    assert report.leads_processed == 2
    assert report.leads_qualified == 1
    assert report.leads_not_qualified == 1
    assert len(report.escalations) == 1
    assert report.injection_attempts_blocked == 1
    assert report.proposals_decided == 1
    assert report.proposals_edited == 1
    assert report.edit_rate == 1.0
    assert report.estimated_human_hours_displaced > 0
