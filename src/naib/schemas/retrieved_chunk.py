from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    """One nearest-neighbour result from `search_past_proposals`."""

    proposal_label: str
    scope_section: str
    chunk_text: str
    distance: float
