"""Deterministic half of the red-team suite: does `scan_for_injection`
flag every attack string in naib/data/redteam_corpus.json, and correctly
leave clean controls alone. Zero cost, runs on every commit (docs/EVALS.md
'Unit ... Deterministic'). The real-model half (does a live agent run
actually resist manipulation) is naib.evals.redteam / this same
directory's test_corpus_full_pipeline.py, marked -m redteam.
"""

import pytest

from naib.evals.redteam import load_redteam_corpus
from naib.guardrails.injection import scan_for_injection
from naib.schemas.redteam_case import RedTeamCase

_CORPUS = load_redteam_corpus()


@pytest.mark.parametrize("case", _CORPUS, ids=[c.id for c in _CORPUS])
def test_injection_scan_matches_expected_outcome(case: RedTeamCase) -> None:
    result = scan_for_injection(case.text)
    assert result.flagged is case.expect_injection_flagged, (
        f"{case.id} ({case.category}): expected flagged={case.expect_injection_flagged}, "
        f"got {result.flagged} — patterns matched: {result.matched_patterns}"
    )


def test_every_attack_category_from_the_agent_definition_is_covered() -> None:
    """See .claude/agents/injection-red-teamer.md — the 9 attack classes it
    names. This test fails loudly if a category silently drops out of the
    corpus during future edits."""

    categories = {case.category for case in _CORPUS}
    required_substrings = [
        "direct_override",
        "hidden_in",
        "delimiter_escape",
        "encoded",
        "price_manipulation",
        "authority_spoofing",
        "data_exfiltration",
        "roman_urdu",
    ]
    for substring in required_substrings:
        assert any(substring in category for category in categories), (
            f"no red-team corpus case covers {substring!r}"
        )
