"""ProposalAgent's four output guardrails (docs/ARCHITECTURE.md guardrail
inventory). Output guardrails run once, on the agent producing final output
— see CLAUDE.md's guardrail-placement note. Registered as four separately
named guardrails, not one combined check, so each shows up individually in
the trace (docs/EVALS.md wants every guardrail outcome visible) — the same
convention Phase 2 used for IntakeAgent's four input guardrails.

All four are deterministic first-pass checks (docs/EVALS.md 'Deterministic
before rubric'); a genuine semantic capability-claim check needs an LLM
rubric grader, which is Phase 6's eval-suite territory, not a real-time
guardrail.
"""

import re
from collections.abc import Callable
from typing import Any

from agents import GuardrailFunctionOutput, OutputGuardrail, RunContextWrapper
from agents.agent import Agent

from naib.playbook import get_playbook_entry, load_playbook, render_price_band
from naib.schemas.proposal_draft import ProposalDraft
from naib.settings import get_settings

_COMMITMENT_PATTERNS = [
    r"\bguarantee[ds]?\b",
    r"\bwe promise\b",
    r"\bcontractually\b",
    r"\bwarrant(y|ies)\b",
    r"\bcommit(ted)? to delivering\b",
    r"\bby (january|february|march|april|may|june|july|august|september|october|november|"
    r"december) \d{1,2}",
    r"\bno later than\b",
]
_COMMITMENT_COMPILED = [re.compile(p, re.IGNORECASE) for p in _COMMITMENT_PATTERNS]

_MIN_DRAFT_CHARS = 100
_MAX_DRAFT_CHARS = 3000
_MAX_EM_DASHES = 3
_GREETING_PATTERN = re.compile(r"\b(hi|hello|dear|assalam)\b", re.IGNORECASE)
_SIGNOFF_PATTERN = re.compile(r"\b(regards|best|thanks|sincerely|thank you)\b", re.IGNORECASE)


def _non_proposal_output_reason(output: Any) -> str | None:
    if not isinstance(output, ProposalDraft):
        return "output is not a ProposalDraft"
    return None


def price_floor_check(draft: ProposalDraft) -> str | None:
    """Return a trip reason, or None if the price is clean. CLAUDE.md rule
    4: the model may select a band, never compute one — so the check is an
    exact match against the playbook's own canonical string, not parsing
    and re-validating a number the model produced."""

    try:
        entry = get_playbook_entry(draft.playbook_entry_id)
    except KeyError:
        return f"playbook_entry_id {draft.playbook_entry_id!r} does not exist"

    expected = render_price_band(entry)
    if draft.price_band != expected:
        return f"price_band {draft.price_band!r} does not match playbook band {expected!r}"

    settings = get_settings()
    if entry.price_band_low < settings.price_floor_pkr:
        return (
            f"playbook entry's own floor ({entry.price_band_low}) is below the "
            f"configured price floor ({settings.price_floor_pkr})"
        )
    return None


def capability_claim_check(draft: ProposalDraft) -> str | None:
    """Deterministic first pass: flag any capability keyword from *another*
    playbook entry appearing in the draft that isn't in the selected
    entry's own capability list. Catches cross-entry hallucination; does
    not catch a wholly novel invented capability — that needs a rubric
    grader (Phase 6)."""

    try:
        entry = get_playbook_entry(draft.playbook_entry_id)
    except KeyError:
        return f"playbook_entry_id {draft.playbook_entry_id!r} does not exist"

    allowed = {c.lower() for c in entry.capabilities}
    all_known = {c.lower() for e in load_playbook() for c in e.capabilities}
    draft_lower = draft.draft_md.lower()

    for capability in sorted(all_known - allowed):
        if capability in draft_lower:
            return f"draft claims capability {capability!r}, not in {entry.id}'s capability list"
    return None


def no_commitment_check(draft: ProposalDraft) -> str | None:
    for pattern in _COMMITMENT_COMPILED:
        if pattern.search(draft.draft_md):
            return f"draft contains binding-commitment language matching {pattern.pattern!r}"
    return None


def tone_and_length_check(draft: ProposalDraft) -> str | None:
    text = draft.draft_md
    if not (_MIN_DRAFT_CHARS <= len(text) <= _MAX_DRAFT_CHARS):
        return f"draft length {len(text)} outside [{_MIN_DRAFT_CHARS}, {_MAX_DRAFT_CHARS}]"
    if not _GREETING_PATTERN.search(text[:200]):
        return "draft is missing a recognisable greeting near the start"
    if not _SIGNOFF_PATTERN.search(text[-200:]):
        return "draft is missing a recognisable sign-off near the end"
    if text.count("—") > _MAX_EM_DASHES:
        return "draft over-uses em-dashes (house style)"
    return None


def _make_output_guardrail(
    name: str, check: Callable[[ProposalDraft], str | None]
) -> OutputGuardrail[Any]:
    async def _run(
        ctx: RunContextWrapper[Any], agent: Agent[Any], output: Any
    ) -> GuardrailFunctionOutput:
        not_proposal = _non_proposal_output_reason(output)
        if not_proposal is not None:
            return GuardrailFunctionOutput(
                output_info={"reason": not_proposal}, tripwire_triggered=True
            )
        reason = check(output)
        return GuardrailFunctionOutput(
            output_info={"reason": reason} if reason else {}, tripwire_triggered=reason is not None
        )

    return OutputGuardrail(guardrail_function=_run, name=name)


price_floor_guardrail = _make_output_guardrail("price_floor", price_floor_check)
capability_claim_guardrail = _make_output_guardrail("capability_claim", capability_claim_check)
no_commitment_guardrail = _make_output_guardrail("no_commitment", no_commitment_check)
tone_and_length_guardrail = _make_output_guardrail("tone_and_length", tone_and_length_check)

PROPOSAL_OUTPUT_GUARDRAILS: list[OutputGuardrail[Any]] = [
    price_floor_guardrail,
    capability_claim_guardrail,
    no_commitment_guardrail,
    tone_and_length_guardrail,
]
