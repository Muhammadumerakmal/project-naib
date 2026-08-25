from pydantic import BaseModel


class EnrichmentResult(BaseModel):
    """EnrichmentAgent's structured return value (agent-as-tool — see
    docs/ARCHITECTURE.md, this returns to the Qualifier, it does not hand
    off)."""

    company_name: str | None = None
    website_url: str | None = None
    detected_stack: list[str]
    company_size_estimate: str | None = None
    summary: str
    confidence: float
    reasons: list[str]
