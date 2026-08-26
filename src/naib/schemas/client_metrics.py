from pydantic import BaseModel


class MetricsPoint(BaseModel):
    date: str  # ISO date, one bucket per calendar day
    value: float


class ClientMetrics(BaseModel):
    """Dashboard chart data — PLAN.md Phase 7: 'edit rate over time, cost
    per lead, injections blocked, time-to-first-response'."""

    edit_rate_over_time: list[MetricsPoint]
    cost_per_lead_over_time: list[MetricsPoint]
    injections_blocked_total: int
    avg_time_to_first_response_seconds: float | None
