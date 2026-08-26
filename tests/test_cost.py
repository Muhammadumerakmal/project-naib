from naib.cost import estimate_cost_usd


def test_estimate_cost_usd_known_model() -> None:
    cost = estimate_cost_usd("gpt-4.1-mini", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 0.40 + 1.60


def test_estimate_cost_usd_unknown_model_is_zero() -> None:
    assert estimate_cost_usd("some-future-model", input_tokens=1000, output_tokens=1000) == 0.0


def test_estimate_cost_usd_none_model_is_zero() -> None:
    assert estimate_cost_usd(None, input_tokens=1000, output_tokens=1000) == 0.0


def test_estimate_cost_usd_zero_tokens_is_zero() -> None:
    assert estimate_cost_usd("gpt-4.1", input_tokens=0, output_tokens=0) == 0.0
