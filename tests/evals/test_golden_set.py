"""Golden-set agreement suite. `-m eval` only (docs/EVALS.md), never run by
plain `pytest` or CI's unit step. Requires a real OPENAI_API_KEY and spends
real money — the synthetic records in naib/data/golden_set.json prove the
runner and thresholds are wired correctly; the numbers only become real once
Umer's 60 labelled leads (PLAN.md Phase 2 [YOU]) replace them, the same
self-expiring pattern as the Phase 1 playbook placeholder.
"""

import pytest

from naib.evals.golden_set import load_golden_set, run_golden_set
from naib.store.models import Client

pytestmark = pytest.mark.eval


async def test_synthetic_golden_set_runner_is_wired() -> None:
    """Not a claim about real-world accuracy — a claim that the runner
    itself produces the metrics docs/EVALS.md expects, end to end against a
    real model. Thresholds here are placeholders; PLAN.md's real ≥85% /
    ≥95% / ≥80% gate applies once the golden set is real."""

    records = load_golden_set()
    assert all(r.is_synthetic for r in records)

    client = Client(name="Synthetic Eval Client", plan="pilot", playbook_version="v0")
    metrics = await run_golden_set(records, client)

    assert metrics.total == len(records)
    assert 0.0 <= metrics.qualification_agreement <= 1.0
    assert 0.0 <= metrics.escalation_recall <= 1.0
    assert 0.0 <= metrics.escalation_precision <= 1.0
