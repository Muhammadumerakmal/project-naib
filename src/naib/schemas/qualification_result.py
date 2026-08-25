from pydantic import BaseModel


class QualificationResult(BaseModel):
    """QualifierAgent's structured output — ICP rubric score plus the
    routing decision. See docs/ARCHITECTURE.md § Agent topology."""

    qualified: bool
    score: float
    band: str
    disqualifiers: list[str]
    should_escalate: bool
    confidence: float
    reasons: list[str]
