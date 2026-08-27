"""The risk calculator -- docs/DEPLOYABILITY.md § 1 'Make risk the enemy':
populated live during discovery, it makes *doing nothing* expensive on
paper, because that is what Naib is actually competing against, not
another vendor. Pure math, no I/O -- naib.cli or a future dashboard screen
can front it; keeping it framework-free keeps it easy to also hand-run in
a spreadsheet during a call if that's faster than opening a terminal.
"""

from dataclasses import dataclass


@dataclass
class RiskCalculatorInputs:
    monthly_enquiries: int
    avg_hours_to_first_response: float
    pct_enquiries_never_replied: float  # 0..1 -- "the number that hurts"
    close_rate: float  # 0..1, of enquiries that *did* get a reply
    avg_deal_value: float
    human_cost_per_month: float
    naib_cost_per_month: float

    def __post_init__(self) -> None:
        for name, value in (
            ("pct_enquiries_never_replied", self.pct_enquiries_never_replied),
            ("close_rate", self.close_rate),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1, got {value}")
        if self.monthly_enquiries < 0:
            raise ValueError("monthly_enquiries must be >= 0")


@dataclass
class RiskCalculatorResult:
    inputs: RiskCalculatorInputs
    leads_never_replied_per_month: float
    estimated_monthly_leakage: float
    estimated_annual_leakage: float
    # Leakage recovered per dollar spent on Naib -- None when naib_cost_per_month
    # is 0 (division is undefined, not infinite -- don't print a lie).
    naib_payback_multiple: float | None


def calculate_leakage_risk(inputs: RiskCalculatorInputs) -> RiskCalculatorResult:
    """Estimated leakage = enquiries x no-reply% x close-rate x deal value
    -- the exact formula in docs/DEPLOYABILITY.md's build artifact."""

    leads_never_replied = inputs.monthly_enquiries * inputs.pct_enquiries_never_replied
    monthly_leakage = leads_never_replied * inputs.close_rate * inputs.avg_deal_value

    return RiskCalculatorResult(
        inputs=inputs,
        leads_never_replied_per_month=leads_never_replied,
        estimated_monthly_leakage=monthly_leakage,
        estimated_annual_leakage=monthly_leakage * 12,
        naib_payback_multiple=(
            monthly_leakage / inputs.naib_cost_per_month
            if inputs.naib_cost_per_month > 0
            else None
        ),
    )


def render_risk_summary(result: RiskCalculatorResult, *, currency: str = "PKR") -> str:
    """Markdown table for pasting straight into a proposal -- fills in the
    blanks of docs/DEPLOYABILITY.md's discovery-call table with real
    numbers from one prospect."""

    i = result.inputs
    payback = (
        f"{result.naib_payback_multiple:.1f}x"
        if result.naib_payback_multiple is not None
        else "n/a (Naib cost not set)"
    )
    return f"""| | |
|---|---|
| Inbound enquiries / month | {i.monthly_enquiries} |
| Average time to first response | {i.avg_hours_to_first_response:.1f} hours |
| Enquiries that never got a reply | {i.pct_enquiries_never_replied:.0%} |
| Average deal value | {currency} {i.avg_deal_value:,.0f} |
| **Estimated monthly leakage** | **{currency} {result.estimated_monthly_leakage:,.0f}** |
| Estimated annual leakage | {currency} {result.estimated_annual_leakage:,.0f} |
| Cost of a person doing this properly | {currency} {i.human_cost_per_month:,.0f}/month |
| Naib cost | {currency} {i.naib_cost_per_month:,.0f}/month |
| Leakage recovered per Naib dollar | {payback} |
"""
