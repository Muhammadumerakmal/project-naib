"""Read-only tools available to `IntakeAgent`. CLAUDE.md rule 1: any agent
that reads untrusted content runs with a read-only tool set — nothing in
this module writes anything or requires approval. See docs/ARCHITECTURE.md
§ Tools, safe tier.
"""

import re
import uuid

from agents import function_tool
from sqlmodel import select

from naib.schemas.contact_extraction import ContactExtraction
from naib.store.db import get_sessionmaker
from naib.store.models import Lead

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE = re.compile(r"(?:\+92|0)3\d{2}[-\s]?\d{7}")


@function_tool
def extract_contact_info(text: str) -> ContactExtraction:
    """Deterministically extract email addresses and Pakistani mobile
    numbers from the message text. Use this to cross-check contact details
    rather than relying only on your own reading."""

    return ContactExtraction(
        emails=list(dict.fromkeys(_EMAIL.findall(text))),
        phones=list(dict.fromkeys(_PHONE.findall(text))),
    )


@function_tool
async def lookup_existing_lead(client_id: str, contact_email: str) -> bool:
    """Check whether this client already has a prior lead from this contact
    email. Existing-client threads are a hard escalation trigger
    (docs/ARCHITECTURE.md § 'does not own' / escalates when)."""

    async with get_sessionmaker()() as session:
        statement = select(Lead).where(
            Lead.client_id == uuid.UUID(client_id),
            Lead.normalized["contact_email"].astext  # type: ignore[index]
            == contact_email,  # why: JSONB key lookup has no typed accessor in SQLModel
        )
        rows = (await session.exec(statement)).all()
    return len(rows) > 0
