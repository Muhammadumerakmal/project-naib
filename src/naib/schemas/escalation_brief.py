from pydantic import BaseModel


class EscalationBrief(BaseModel):
    """EscalationAgent's structured output — a brief a human can act on in
    30 seconds: what came in, what it concluded, exactly why it stopped,
    what it recommends. See docs/ARCHITECTURE.md § Agent topology."""

    reason: str
    summary: str
    conclusion: str
    why_stopped: str
    recommendation: str
    confidence: float
    reasons: list[str]
