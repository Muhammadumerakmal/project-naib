"""The run context threaded through `Runner.run(..., context=...)` for the
intake -> qualifier pipeline. Carries per-run state that isn't part of the
conversation itself: which client this lead belongs to, the language
guardrail already detected, and (once `IntakeAgent` hands off) the validated
`NormalizedLead` — never the raw untrusted text.
"""

import uuid
from dataclasses import dataclass

from naib.schemas.normalized_lead import NormalizedLead
from naib.store.models import Client


@dataclass
class NaibContext:
    client: Client
    lead_id: uuid.UUID
    language: str
    normalized_lead: NormalizedLead | None = None
