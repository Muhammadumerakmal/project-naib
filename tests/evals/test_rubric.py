"""Rubric grader suite. `-m eval` only (docs/EVALS.md), real model calls,
never run by plain `pytest` or CI's unit step.
"""

import pytest

from naib.evals.rubric import grade_escalation_usefulness, grade_proposal_quality, grade_tone_match

pytestmark = pytest.mark.eval

_SAMPLE_PROPOSAL = (
    "Hi Ali,\n\nThanks for reaching out. We'd build a 5-page marketing site covering your "
    "clinic's services, with one round of revisions included.\n\nInvestment: PKR 40,000 - "
    "PKR 99,999.\n\nBest regards,\nNaib"
)
_SAMPLE_ESCALATION = (
    "# Escalation — existing_client\n\n**What came in:** Sender asked us to fix a bug on a "
    "site we already built.\n\n**What the pipeline concluded:** Disqualified: existing-client "
    "thread.\n\n**Why it stopped here:** Hard disqualifier 'existing_client' fired.\n\n"
    "**Recommendation:** Route to account management, not sales."
)


async def test_grade_proposal_quality_returns_a_scored_rubric() -> None:
    score = await grade_proposal_quality(_SAMPLE_PROPOSAL)
    assert 1 <= score.score <= 5
    assert score.justification


async def test_grade_escalation_usefulness_returns_a_scored_rubric() -> None:
    score = await grade_escalation_usefulness(_SAMPLE_ESCALATION)
    assert 1 <= score.score <= 5
    assert score.justification


async def test_grade_tone_match_returns_a_scored_rubric() -> None:
    score = await grade_tone_match(_SAMPLE_PROPOSAL)
    assert 1 <= score.score <= 5
    assert score.justification
