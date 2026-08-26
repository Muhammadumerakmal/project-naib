"""Append-only event writer. Every run writes a structured event to
agent_events: input hash, agent, tool calls, guardrail outcomes, model,
tokens, cost, latency, and the final decision with its reason string. See
CLAUDE.md rule 3 and docs/ARCHITECTURE.md § Data model.
"""

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from agents.usage import Usage

from naib.cost import estimate_cost_usd
from naib.store.db import get_sessionmaker
from naib.store.models import AgentEvent


@dataclass
class RunRecord:
    """Mutable scratchpad the caller fills in during a run. `record_run`
    writes it to `agent_events` as one row of event_type='run' on exit."""

    run_id: uuid.UUID
    agent: str
    lead_id: uuid.UUID | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)  # why: freeform event context
    outcome: str = "success"


@asynccontextmanager
async def record_run(
    agent: str,
    lead_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
) -> AsyncIterator[RunRecord]:
    """Wrap one agent run. Writes exactly one `agent_events` row on exit:
    outcome='success' if the block completed, 'error' (with the exception
    message in payload) if it raised — the exception is re-raised either way,
    a tripwire must never become a swallowed error."""

    record = RunRecord(run_id=run_id or uuid.uuid4(), agent=agent, lead_id=lead_id)
    started = time.monotonic()
    try:
        yield record
    except Exception as exc:
        record.outcome = "error"
        record.payload = {**record.payload, "error": str(exc)}
        raise
    finally:
        latency_ms = int((time.monotonic() - started) * 1000)
        event = AgentEvent(
            run_id=record.run_id,
            lead_id=record.lead_id,
            agent=record.agent,
            event_type="run",
            outcome=record.outcome,
            model=record.model,
            tokens_in=record.tokens_in,
            tokens_out=record.tokens_out,
            cost_usd=record.cost_usd,
            latency_ms=latency_ms,
            payload=record.payload,
        )
        async with get_sessionmaker()() as session:
            session.add(event)
            await session.commit()


def record_usage(record: RunRecord, *, model: str | None, usage: Usage) -> None:
    """Fill tokens_in/tokens_out/cost_usd on a RunRecord from an SDK
    `Usage` (e.g. `result.context_wrapper.usage` after `Runner.run`). Every
    pipeline calls this so `agent_events.cost_usd` is real, not always
    None — the Phase 6 budget suite (docs/EVALS.md) depends on it."""

    record.model = model
    record.tokens_in = usage.input_tokens
    record.tokens_out = usage.output_tokens
    record.cost_usd = estimate_cost_usd(
        model, input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
    )


async def record_event(
    *,
    run_id: uuid.UUID,
    agent: str,
    event_type: str,
    lead_id: uuid.UUID | None = None,
    tool: str | None = None,
    guardrail: str | None = None,
    outcome: str | None = None,
    payload: dict[str, Any] | None = None,  # why: freeform event context
) -> None:
    """Record one sub-event (a tool call, a guardrail outcome) within a run —
    independent of, and in addition to, the single row `record_run` writes
    for the run as a whole."""

    event = AgentEvent(
        run_id=run_id,
        lead_id=lead_id,
        agent=agent,
        event_type=event_type,
        tool=tool,
        guardrail=guardrail,
        outcome=outcome,
        payload=payload or {},
    )
    async with get_sessionmaker()() as session:
        session.add(event)
        await session.commit()
