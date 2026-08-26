"""Real-model half of the red-team suite. `-m redteam` only (docs/EVALS.md),
never run by plain `pytest` or CI's unit step — requires a real
OPENAI_API_KEY and spends real money. The deterministic half in
test_corpus_deterministic.py already proves the pattern-matching layer on
every commit at zero cost; this proves a live model actually resists
manipulation end to end.
"""

import pytest

from naib.evals.redteam import load_redteam_corpus, run_redteam_corpus
from naib.store.models import Client

pytestmark = pytest.mark.redteam


async def test_redteam_corpus_full_pipeline_zero_failures() -> None:
    """Pass condition is absolute (docs/EVALS.md): every case either trips
    a guardrail as expected, or produces a QualificationResult that was not
    manipulated by the attack. 'Mostly blocked' is a failure."""

    cases = load_redteam_corpus()
    client = Client(name="Red Team Client", plan="pilot", playbook_version="v0")

    report = await run_redteam_corpus(cases, client)

    assert report.all_passed, (
        f"{len(report.failures)}/{report.total} red-team cases failed: "
        + "; ".join(f"{f.case_id} ({f.category}): {f.reason}" for f in report.failures)
    )
