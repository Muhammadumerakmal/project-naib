"""Kill switch exercised through the real arq queue, not a direct function
call (contrast tests/test_worker.py's test_process_lead_halts_when_kill_
switch_is_active, which calls naib.worker.process_lead(...) in-process).
This enqueues onto real Redis and runs an actual arq Worker in burst mode
to dequeue and dispatch it -- exercising serialization and the real worker
loop. PLAN.md Phase 8: 'Kill switch tested in production conditions.'

What this does NOT cover: a job that is already mid-execution when the
switch flips. naib.worker._kill_switch_active's docstring is explicit that
the guarantee is 'a queued job that hasn't started yet simply never
starts,' not an abort of an in-flight run -- there is nothing further to
build here, this test just proves that guarantee holds through the real
queue rather than only through a direct call.
"""

import uuid

import pytest
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker

from naib import worker as worker_module
from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead


async def _make_client_with_kill_switch(*, enabled: bool) -> Client:
    async with get_sessionmaker()() as session:
        client = Client(
            name="Integration Kill Switch Agency",
            plan="pilot",
            playbook_version="v0",
            kill_switch=enabled,
        )
        session.add(client)
        await session.commit()
        await session.refresh(client)
    return client


async def test_kill_switch_halts_a_job_dequeued_from_real_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = await _make_client_with_kill_switch(enabled=True)
    async with get_sessionmaker()() as session:
        lead = Lead(client_id=client.id, channel="email", raw_hash=str(uuid.uuid4()))
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    async def _boom(**kwargs: object) -> object:
        raise AssertionError("run_intake_qualifier should never run for a killed client")

    monkeypatch.setattr(worker_module, "run_intake_qualifier", _boom)

    pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    arq_worker = Worker(
        functions=[worker_module.process_lead], redis_pool=pool, burst=True, poll_delay=0.1
    )
    try:
        job = await pool.enqueue_job("process_lead", str(lead.id), str(client.id), "hi", "email")
        assert job is not None

        await arq_worker.async_run()
        result = await job.result(timeout=5)
    finally:
        await arq_worker.close()  # closes the pool too -- do this last

    assert result == "halted:kill_switch"
