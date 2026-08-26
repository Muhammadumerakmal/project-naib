"""Approximate per-model USD cost, for `agent_events.cost_usd` and the
Phase 6 budget suite (docs/EVALS.md 'Cost per lead <= budget'). No live
pricing API exists for this; these are point-in-time published rates and
need updating if OpenAI's pricing changes — same approach every
cost-tracking integration in this ecosystem takes.
"""

# (input $ / 1M tokens, output $ / 1M tokens)
_PRICING_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "whisper-1": (0.0, 0.0),  # priced per audio-minute, not tokens — tracked separately
    "text-embedding-3-small": (0.02, 0.0),
}


def estimate_cost_usd(model: str | None, *, input_tokens: int, output_tokens: int) -> float:
    if model is None:
        return 0.0
    input_price, output_price = _PRICING_PER_MILLION_TOKENS.get(model, (0.0, 0.0))
    return (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price
