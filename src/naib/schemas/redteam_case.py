from pydantic import BaseModel


class RedTeamCase(BaseModel):
    """One attack (or clean control) string from naib/data/redteam_corpus.json.
    See docs/EVALS.md § Red team suite and .claude/agents/injection-red-teamer.md
    for the category list this corpus tracks."""

    id: str
    category: str
    text: str
    expect_injection_flagged: bool
