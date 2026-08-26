"""Follow-up cadence: find approved proposals due for a nudge, draft one
attempt, gate on the attempt cap, and hand cleanly back to a human once
exhausted. See PLAN.md Phase 5.

Known gap, disclosed rather than silently assumed away: there is no
inbound-reply-matching mechanism yet (matching a new inbound message back
to an existing lead thread), so `find_eligible_followups` cannot exclude a
proposal that already got a reply — it only knows "approved" and "how long
since last contact." Building real reply-detection is bigger than PLAN.md
scopes for Phase 5 and needs its own design pass.
"""

import uuid
from datetime import UTC, datetime, timedelta

from agents import Runner
from sqlmodel import select

from naib.agents.context import NaibContext
from naib.agents.followup import build_followup_agent
from naib.approvals import request_approval
from naib.events import record_run, record_usage
from naib.schemas.followup_draft import FollowUpDraft
from naib.sessions import PostgresSession
from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, FollowUp, Lead, Proposal


async def find_eligible_followups() -> list[uuid.UUID]:
    settings = get_settings()
    interval = timedelta(days=settings.followup_interval_days)
    now = datetime.now(UTC)

    async with get_sessionmaker()() as session:
        proposals = (
            await session.exec(select(Proposal).where(Proposal.approved_by.is_not(None)))  # type: ignore[union-attr]
        ).all()

        eligible: list[uuid.UUID] = []
        for proposal in proposals:
            followups = (
                await session.exec(
                    select(FollowUp)
                    .where(FollowUp.proposal_id == proposal.id)
                    .order_by(FollowUp.created_at.desc())  # type: ignore[attr-defined]
                )
            ).all()
            if len(followups) >= settings.max_followup_attempts:
                continue

            last_contact = followups[0].created_at if followups else proposal.approved_at
            if last_contact is not None and now - last_contact >= interval:
                eligible.append(proposal.id)

        return eligible


async def run_followup_pipeline(*, proposal_id: uuid.UUID) -> FollowUp:
    settings = get_settings()

    async with get_sessionmaker()() as session:
        proposal = (await session.exec(select(Proposal).where(Proposal.id == proposal_id))).one()
        lead = (await session.exec(select(Lead).where(Lead.id == proposal.lead_id))).one()
        client = (await session.exec(select(Client).where(Client.id == lead.client_id))).one()
        prior_followups = (
            await session.exec(select(FollowUp).where(FollowUp.proposal_id == proposal_id))
        ).all()

    attempt_number = len(prior_followups) + 1
    if attempt_number > settings.max_followup_attempts:
        raise ValueError(
            f"Follow-up exhausted for proposal {proposal_id} "
            f"(max {settings.max_followup_attempts} attempts already used)"
        )

    last_contact_times = [f.created_at for f in prior_followups]
    if proposal.approved_at is not None:
        last_contact_times.append(proposal.approved_at)
    last_contact = max(last_contact_times) if last_contact_times else None
    days_since = (datetime.now(UTC) - last_contact).days if last_contact is not None else None

    agent = build_followup_agent()
    context = NaibContext(client=client, lead_id=lead.id, language=lead.language or "en")
    lead_session = PostgresSession(lead.id)

    summary = (
        f"Original proposal price band: {proposal.price_band}\n"
        f"Original proposal draft:\n{proposal.draft_md}\n\n"
        f"This is attempt number {attempt_number} of {settings.max_followup_attempts}.\n"
        f"Days since last contact: {days_since if days_since is not None else 'unknown'}\n"
    )

    async with record_run(agent="FollowUpAgent", lead_id=lead.id) as record:
        result = await Runner.run(agent, summary, context=context, session=lead_session)
        model = agent.model if isinstance(agent.model, str) else None
        record_usage(record, model=model, usage=result.context_wrapper.usage)

    draft = result.final_output
    if not isinstance(draft, FollowUpDraft):
        raise TypeError(
            f"FollowUpAgent ended without a FollowUpDraft (got {type(draft).__name__})."
        )

    async with get_sessionmaker()() as session:
        followup = FollowUp(
            proposal_id=proposal_id, attempt_number=attempt_number, message_md=draft.message_md
        )
        session.add(followup)
        await session.commit()
        await session.refresh(followup)

    await request_approval(entity_type="followup", entity_id=followup.id, action="send_followup")

    if attempt_number == settings.max_followup_attempts:
        async with get_sessionmaker()() as session:
            session.add(
                Escalation(
                    lead_id=lead.id,
                    reason="followup_exhausted",
                    brief_md=(
                        "# Escalation — follow-up cadence exhausted\n\n"
                        f"Proposal {proposal_id} has reached its final follow-up attempt "
                        f"({settings.max_followup_attempts}) with no recorded reply. Naib will "
                        "not draft further follow-ups for this proposal — a human needs to "
                        "decide whether to reach out personally or let it lapse."
                    ),
                )
            )
            await session.commit()

    return followup
