import pytest

from naib.sales.risk_calculator import (
    RiskCalculatorInputs,
    calculate_leakage_risk,
    render_risk_summary,
)


def _inputs(**overrides: object) -> RiskCalculatorInputs:
    defaults: dict[str, object] = dict(
        monthly_enquiries=100,
        avg_hours_to_first_response=18.0,
        pct_enquiries_never_replied=0.3,
        close_rate=0.2,
        avg_deal_value=100_000.0,
        human_cost_per_month=80_000.0,
        naib_cost_per_month=40_000.0,
    )
    defaults.update(overrides)
    return RiskCalculatorInputs(**defaults)  # type: ignore[arg-type]


def test_calculate_leakage_risk_applies_the_documented_formula() -> None:
    result = calculate_leakage_risk(_inputs())

    # 100 * 0.3 = 30 never-replied leads
    assert result.leads_never_replied_per_month == pytest.approx(30.0)
    # 30 * 0.2 close-rate * 100,000 deal value
    assert result.estimated_monthly_leakage == pytest.approx(600_000.0)
    assert result.estimated_annual_leakage == pytest.approx(7_200_000.0)
    assert result.naib_payback_multiple == pytest.approx(15.0)


def test_naib_payback_multiple_is_none_when_naib_cost_is_zero() -> None:
    result = calculate_leakage_risk(_inputs(naib_cost_per_month=0.0))

    assert result.naib_payback_multiple is None


@pytest.mark.parametrize(
    "field", ["pct_enquiries_never_replied", "close_rate"]
)
def test_rejects_out_of_range_percentages(field: str) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        _inputs(**{field: 1.5})


def test_rejects_negative_enquiries() -> None:
    with pytest.raises(ValueError, match="monthly_enquiries"):
        _inputs(monthly_enquiries=-1)


def test_render_risk_summary_includes_the_key_numbers() -> None:
    result = calculate_leakage_risk(_inputs())

    summary = render_risk_summary(result)

    assert "600,000" in summary
    assert "15.0x" in summary
    assert "30%" in summary


def test_render_risk_summary_handles_no_naib_cost() -> None:
    result = calculate_leakage_risk(_inputs(naib_cost_per_month=0.0))

    summary = render_risk_summary(result)

    assert "n/a" in summary
