import uuid
from datetime import datetime

from pydantic import BaseModel


class ApprovalSummary(BaseModel):
    """One row in the dashboard's approval queue — docs/PLAN.md Phase 7,
    'the daily-driver screen'. `preview` is a short, human-readable excerpt
    of the underlying draft so a reviewer doesn't need a second click just
    to triage the queue."""

    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    action: str
    lead_id: uuid.UUID
    requested_at: datetime
    decided_at: datetime | None
    decided_by: str | None
    decision: str | None
    preview: str
    full_text: str
