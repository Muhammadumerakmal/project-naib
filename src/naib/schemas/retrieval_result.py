from pydantic import BaseModel


class RetrievalResult(BaseModel):
    """RetrievalAgent's structured return value (agent-as-tool, same
    reasoning as EnrichmentResult — see docs/ARCHITECTURE.md)."""

    relevant_excerpts: list[str]
    summary: str
    confidence: float
    reasons: list[str]
