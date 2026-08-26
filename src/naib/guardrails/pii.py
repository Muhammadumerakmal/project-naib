"""PII minimisation. CNIC, passport, and card numbers are redacted from
inbound text *before* it is wrapped and handed to any agent or persisted to
session storage — see docs/ARCHITECTURE.md guardrail inventory,
`pii_minimize`.

Judgment call: unlike `injection_scan`, this guardrail's job is to mutate the
text, not merely flag it. The SDK's `InputGuardrail` hook observes input, it
does not rewrite what the agent sees — so the real redaction happens in
`redact_pii`, called by the intake pipeline *before* `Runner.run`. The
`InputGuardrail` wrapper below exists for tracing/observability (docs/
EVALS.md wants every guardrail outcome in the trace) and never trips a
tripwire: finding PII in an inbound lead is expected and handled by
redaction, not a reason to halt the run.
"""

import re
from typing import Any  # why: guardrail is context-agnostic, must bind to any agent's TContext

from agents import GuardrailFunctionOutput, InputGuardrail, RunContextWrapper
from agents.agent import Agent
from agents.items import TResponseInputItem

# CNIC: 5-7-1 digit groups, with or without dashes.
_CNIC = re.compile(r"\b\d{5}-?\d{7}-?\d\b")
# Pakistani passport: one letter followed by 7-8 digits.
_PASSPORT = re.compile(r"\b[A-Za-z]\d{7,8}\b")
# Card numbers: 13-19 digits, optionally grouped in 4s with spaces/dashes.
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")

_PATTERNS: dict[str, re.Pattern[str]] = {
    "cnic": _CNIC,
    "passport": _PASSPORT,
    "card": _CARD,
}


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Replace CNIC/passport/card-like substrings with a labelled
    placeholder. Returns the redacted text and the list of PII types found,
    in match order, so the caller can log what was scrubbed without logging
    the value itself."""

    redacted = text
    found: list[str] = []
    for label, pattern in _PATTERNS.items():
        matches = pattern.findall(redacted)
        if matches:
            found.extend([label] * len(matches))
            redacted = pattern.sub(f"[REDACTED-{label.upper()}]", redacted)
    return redacted, found


async def _pii_minimize(
    ctx: RunContextWrapper[Any],
    agent: Agent[Any],
    agent_input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    text = agent_input if isinstance(agent_input, str) else str(agent_input)
    _, found = redact_pii(text)
    return GuardrailFunctionOutput(output_info={"redacted_types": found}, tripwire_triggered=False)


pii_minimize_guardrail = InputGuardrail(guardrail_function=_pii_minimize, name="pii_minimize")
