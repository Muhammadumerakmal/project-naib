"""arq worker: the API boundary CLAUDE.md means when it says 'catch
InputGuardrailTripwireTriggered at the API boundary and return a structured
refusal + an escalation event.' Webhook handlers only enqueue; this is where
a lead actually runs through the pipeline.
"""

import uuid
from typing import Any

from agents import InputGuardrailTripwireTriggered
from arq.connections import RedisSettings
from sqlmodel import select

from naib.agents.pipeline import run_intake_qualifier
from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation


async def process_lead(
    ctx: dict[str, Any], lead_id: str, client_id: str, raw_text: str, channel: str
) -> str:
    """arq job: run one lead through Intake -> Qualifier. Returns a short
    status string (arq stores job results); the durable record is always the
    Qualification/Escalation row, not the return value."""

    async with get_sessionmaker()() as session:
        client = (await session.exec(select(Client).where(Client.id == uuid.UUID(client_id)))).one()

    try:
        qualification = await run_intake_qualifier(
            lead_id=uuid.UUID(lead_id), client=client, raw_text=raw_text, channel=channel
        )
    except InputGuardrailTripwireTriggered as exc:
        guardrail_name = exc.guardrail_result.guardrail.get_name()
        async with get_sessionmaker()() as session:
            session.add(
                Escalation(
                    lead_id=uuid.UUID(lead_id),
                    reason=f"guardrail_tripwire:{guardrail_name}",
                    brief_md=(
                        f"# Escalation — guardrail tripwire\n\n"
                        f"`{guardrail_name}` tripped on this inbound message before it reached "
                        f"a qualification decision. No agent read past the guardrail boundary. "
                        f"A human needs to read the original message directly."
                    ),
                )
            )
            await session.commit()
        return f"escalated:{guardrail_name}"

    return f"qualified:{qualification.qualified}"


async def _startup(ctx: dict[str, Any]) -> None:
    return None


async def _shutdown(ctx: dict[str, Any]) -> None:
    return None


class WorkerSettings:
    functions = [process_lead]
    on_startup = _startup
    on_shutdown = _shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
