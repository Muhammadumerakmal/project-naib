"""Phase 0 gate test: proves the event writer by running a trivial agent
stand-in and asserting a complete event row lands in Postgres.

Judgment call: real OpenAI Agents SDK agents don't exist until Phase 2 (this
is guardrail scaffolding built *before* any agent exists — see PLAN.md Phase
0), and this suite runs as a deterministic unit test on every commit with no
model call and no API cost (docs/EVALS.md 'Unit ... Every commit ...
Deterministic'). So the 'trivial agent' here is a plain async function that
exercises record_run exactly as a real agent call will in Phase 2: it does
some work, then reports model/tokens/cost onto the yielded RunRecord.
"""

import uuid

import pytest
from agents.usage import Usage
from sqlmodel import select

from naib.events import RunRecord, record_event, record_run, record_usage
from naib.store.db import get_sessionmaker
from naib.store.models import AgentEvent


async def _trivial_agent(record: RunRecord) -> str:
    """Stands in for `Runner.run(some_agent, ...)`: does a unit of work and
    reports its own model/token/cost accounting, exactly as a real agent call
    will once Phase 2 wires the SDK through this same context manager."""

    record.model = "gpt-4.1-mini"
    record.tokens_in = 42
    record.tokens_out = 7
    record.cost_usd = 0.0012
    return "trivial output"


@pytest.mark.asyncio
async def test_record_run_writes_a_complete_event_row() -> None:
    lead_id = uuid.uuid4()

    async with record_run(agent="TrivialAgent", lead_id=lead_id) as record:
        output = await _trivial_agent(record)

    assert output == "trivial output"

    async with get_sessionmaker()() as session:
        rows = (
            await session.exec(select(AgentEvent).where(AgentEvent.run_id == record.run_id))
        ).all()

    assert len(rows) == 1
    event = rows[0]
    assert event.agent == "TrivialAgent"
    assert event.lead_id == lead_id
    assert event.event_type == "run"
    assert event.outcome == "success"
    assert event.model == "gpt-4.1-mini"
    assert event.tokens_in == 42
    assert event.tokens_out == 7
    assert event.cost_usd == pytest.approx(0.0012)
    assert event.latency_ms is not None
    assert event.latency_ms >= 0
    assert event.created_at is not None


@pytest.mark.asyncio
async def test_record_run_reraises_and_still_writes_error_outcome() -> None:
    run_id = uuid.uuid4()

    with pytest.raises(ValueError, match="boom"):
        async with record_run(agent="TrivialAgent", run_id=run_id):
            raise ValueError("boom")

    async with get_sessionmaker()() as session:
        rows = (await session.exec(select(AgentEvent).where(AgentEvent.run_id == run_id))).all()

    assert len(rows) == 1
    assert rows[0].outcome == "error"
    assert rows[0].payload["error"] == "boom"


@pytest.mark.asyncio
async def test_record_event_writes_a_tool_subevent_independent_of_the_run_row() -> None:
    run_id = uuid.uuid4()

    await record_event(
        run_id=run_id,
        agent="TrivialAgent",
        event_type="tool_call",
        tool="fetch_page",
        outcome="success",
        payload={"url": "https://example.com"},
    )

    async with get_sessionmaker()() as session:
        rows = (await session.exec(select(AgentEvent).where(AgentEvent.run_id == run_id))).all()

    assert len(rows) == 1
    assert rows[0].event_type == "tool_call"
    assert rows[0].tool == "fetch_page"
    assert rows[0].payload == {"url": "https://example.com"}


def test_record_usage_fills_tokens_and_cost_from_sdk_usage() -> None:
    record = RunRecord(run_id=uuid.uuid4(), agent="TrivialAgent")

    record_usage(
        record, model="gpt-4.1-mini", usage=Usage(input_tokens=1000, output_tokens=500)
    )

    assert record.model == "gpt-4.1-mini"
    assert record.tokens_in == 1000
    assert record.tokens_out == 500
    assert record.cost_usd is not None
    assert record.cost_usd > 0
