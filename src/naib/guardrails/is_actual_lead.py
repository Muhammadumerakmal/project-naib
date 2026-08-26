"""`is_actual_lead` input guardrail — trips when the inbound message is
spam, a newsletter, an invoice, or an automated notification rather than a
genuine inquiry. Deterministic first pass (docs/EVALS.md 'Deterministic
before rubric'); not exhaustive, grows from real tripwires like the
injection corpus.
"""

import re
from typing import Any  # why: guardrail is context-agnostic, must bind to any agent's TContext

from agents import GuardrailFunctionOutput, InputGuardrail, RunContextWrapper
from agents.agent import Agent
from agents.items import TResponseInputItem

_NOT_A_LEAD_PATTERNS = [
    r"\bunsubscribe\b",
    r"view (this )?in (your )?browser",
    r"\bno-?reply\b",
    r"invoice\s*#?\d+",
    r"this is an automated (message|notification|email)",
    r"your (subscription|order) (has been|is) (confirmed|shipped|cancelled)",
    r"\bnewsletter\b",
    r"terms (and|&) conditions",
    r"privacy policy",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _NOT_A_LEAD_PATTERNS]


def looks_like_non_lead(text: str) -> list[str]:
    """Return the patterns matched. Non-empty means the message looks like
    spam/newsletter/invoice/automated noise rather than a genuine inquiry."""

    return [
        pattern
        for pattern, compiled in zip(_NOT_A_LEAD_PATTERNS, _COMPILED, strict=True)
        if compiled.search(text)
    ]


async def _is_actual_lead(
    ctx: RunContextWrapper[Any],
    agent: Agent[Any],
    agent_input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    text = agent_input if isinstance(agent_input, str) else str(agent_input)
    matched = looks_like_non_lead(text)
    return GuardrailFunctionOutput(
        output_info={"matched_patterns": matched},
        tripwire_triggered=bool(matched),
    )


is_actual_lead_guardrail = InputGuardrail(guardrail_function=_is_actual_lead, name="is_actual_lead")
