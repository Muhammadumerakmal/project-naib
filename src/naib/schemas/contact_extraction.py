from pydantic import BaseModel


class ContactExtraction(BaseModel):
    """Deterministic regex extraction, offered to `IntakeAgent` as a
    read-only tool so it can cross-check its own free-text reading of a
    message against a mechanical pass — see docs/ARCHITECTURE.md tool
    inventory, `extract_contact`."""

    emails: list[str]
    phones: list[str]
