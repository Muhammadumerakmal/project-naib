from pydantic import BaseModel


class ProposalDraft(BaseModel):
    """ProposalAgent's structured output. Selects a price band from the
    playbook — never computes one. See CLAUDE.md rule 4."""

    playbook_entry_id: str
    price_band: str
    scope_summary: str
    draft_md: str
    confidence: float
    reasons: list[str]
