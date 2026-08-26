from pydantic import BaseModel


class FollowUpDraft(BaseModel):
    """FollowUpAgent's structured output — one cadence message, drafted
    only, same as ProposalDraft/EscalationBrief. See PLAN.md Phase 5."""

    message_md: str
    confidence: float
    reasons: list[str]
