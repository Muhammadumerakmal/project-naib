"""Deterministic English / Urdu / Roman Urdu detection. Registered as the
`language_route` input guardrail (docs/ARCHITECTURE.md guardrail inventory)
and used by the intake pipeline to pick the right instruction variant before
the model is ever called — routing has to happen before the agent runs, not
as a side effect of it, so the real behavioural work lives in
`detect_language`; the guardrail wrapper below never trips a tripwire, it
only tags the run for tracing.
"""

import re
import unicodedata
from typing import Any  # why: guardrail is context-agnostic, must bind to any agent's TContext

from agents import GuardrailFunctionOutput, InputGuardrail, RunContextWrapper
from agents.agent import Agent
from agents.items import TResponseInputItem

Language = str  # "en" | "ur" | "roman-ur"

# Urdu script lives in the Arabic Unicode block.
_URDU_SCRIPT_RANGE = re.compile(r"[؀-ۿ]")

# Common Roman Urdu function words / greetings that rarely appear in English
# prose — cheap and far from exhaustive, but catches the bulk of real traffic
# in this market. Grows the same way the injection corpus does: from real
# production tripwires.
_ROMAN_URDU_MARKERS = {
    "hai",
    "hain",
    "kya",
    "aap",
    "ap",
    "kar",
    "karo",
    "krna",
    "chahiye",
    "chahye",
    "mujhe",
    "hum",
    "humein",
    "humko",
    "price",
    "kitna",
    "kitni",
    "assalam",
    "salam",
    "bhai",
    "sir",
    "plz",
    "bnwana",
    "bnwani",
    "website",
    "acha",
    "theek",
    "thk",
}


def detect_language(text: str) -> tuple[Language, float]:
    """Return (language_code, confidence). Urdu script wins outright — it is
    unambiguous. Otherwise score Roman Urdu marker density against word
    count; below a floor of matches we default to English."""

    normalized = unicodedata.normalize("NFKC", text)
    if _URDU_SCRIPT_RANGE.search(normalized):
        return "ur", 0.95

    words = re.findall(r"[a-zA-Z']+", normalized.lower())
    if not words:
        return "en", 0.5

    marker_hits = sum(1 for w in words if w in _ROMAN_URDU_MARKERS)
    density = marker_hits / len(words)

    if marker_hits >= 2 and density >= 0.08:
        return "roman-ur", min(0.5 + density * 2, 0.9)
    return "en", 0.7


async def _language_route(
    ctx: RunContextWrapper[Any],
    agent: Agent[Any],
    agent_input: str | list[TResponseInputItem],
) -> GuardrailFunctionOutput:
    text = agent_input if isinstance(agent_input, str) else str(agent_input)
    language, confidence = detect_language(text)
    return GuardrailFunctionOutput(
        output_info={"language": language, "confidence": confidence},
        tripwire_triggered=False,
    )


language_route_guardrail = InputGuardrail(
    guardrail_function=_language_route, name="language_route"
)
