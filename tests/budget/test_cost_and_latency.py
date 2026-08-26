"""Cost/latency budget suite. `-m budget` only (docs/EVALS.md, nightly),
never run by plain `pytest` or CI's unit step. Requires a real
OPENAI_API_KEY and spends real money.
"""

import pytest

from naib.evals.budget import budget_ceiling_usd, run_budget_check
from naib.evals.golden_set import load_golden_set
from naib.store.models import Client

pytestmark = pytest.mark.budget

_P95_LATENCY_CEILING_MS = 180_000  # docs/EVALS.md: "responds in 3 minutes" claim


async def test_cost_per_lead_within_budget() -> None:
    records = load_golden_set()
    client = Client(name="Budget Test Client", plan="pilot", playbook_version="v0")

    report = await run_budget_check(records, client)
    ceiling = budget_ceiling_usd()

    assert report.max_cost_usd <= ceiling, (
        f"max per-lead cost ${report.max_cost_usd:.4f} exceeds budget ${ceiling:.4f}"
    )


async def test_p95_latency_within_the_three_minute_response_claim() -> None:
    records = load_golden_set()
    client = Client(name="Budget Test Client", plan="pilot", playbook_version="v0")

    report = await run_budget_check(records, client)

    assert report.p95_latency_ms <= _P95_LATENCY_CEILING_MS, (
        f"p95 latency {report.p95_latency_ms}ms exceeds {_P95_LATENCY_CEILING_MS}ms"
    )
