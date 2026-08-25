from pydantic import BaseModel


class NormalizedLead(BaseModel):
    """IntakeAgent's structured output. The only thing downstream agents
    ever see of an inbound message — raw untrusted text stops here. See
    docs/ARCHITECTURE.md § 'The untrusted-text problem'."""

    channel: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    company_name: str | None = None
    message_summary: str
    requested_service: str | None = None
    budget_signal: str | None = None
    language: str
    raw_hash: str
    confidence: float
    reasons: list[str]
