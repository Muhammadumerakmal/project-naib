"""Read-only tools available to `ProposalAgent`. The playbook is the only
source of prices, scope templates, and capabilities — these tools exist so
the model never has to compute or format a number itself (CLAUDE.md rule
4): `lookup_playbook_entry` hands back the exact canonical price-band
string the `price_floor` output guardrail will check for an exact match.
"""

from agents import function_tool
from pydantic import BaseModel

from naib.playbook import get_playbook_entry, load_playbook, render_price_band


class PlaybookEntrySummary(BaseModel):
    id: str
    service_name: str
    description: str


class PlaybookEntryDetail(BaseModel):
    id: str
    service_name: str
    scope_template: str
    capabilities: list[str]
    price_band: str


@function_tool
def list_playbook_entries() -> list[PlaybookEntrySummary]:
    """List every service in the playbook, for picking which one best
    matches the lead's requested service."""

    return [
        PlaybookEntrySummary(id=e.id, service_name=e.service_name, description=e.description)
        for e in load_playbook()
    ]


@function_tool
def lookup_playbook_entry(entry_id: str) -> PlaybookEntryDetail:
    """Look up one playbook entry's scope template, capabilities, and the
    exact canonical price-band string to use verbatim as ProposalDraft's
    price_band — never reformat or recompute it."""

    entry = get_playbook_entry(entry_id)
    return PlaybookEntryDetail(
        id=entry.id,
        service_name=entry.service_name,
        scope_template=entry.scope_template,
        capabilities=entry.capabilities,
        price_band=render_price_band(entry),
    )
