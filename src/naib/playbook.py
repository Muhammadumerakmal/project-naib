"""Playbook loader: the services catalogue, price bands, and scope
templates the ProposalAgent is bound to (Phase 4) — it may select a band
from here, never compute one. See CLAUDE.md rule 4.

Judgment call: naib/data/playbook.json currently holds clearly-labelled
placeholder rows (`is_placeholder=True`), not Umer's real services and
pricing — that data is a `[YOU]` item per PLAN.md Phase 1 nobody else can
supply. Replace the file's contents before Phase 4 needs it for a real
proposal; nothing here enforces that beyond the placeholder flag, so a
Phase 4 output guardrail must check `is_placeholder` before any real quote
goes out.
"""

import json
from functools import lru_cache
from importlib import resources

from naib.schemas.playbook_entry import PlaybookEntry


@lru_cache
def load_playbook() -> list[PlaybookEntry]:
    raw = resources.files("naib.data").joinpath("playbook.json").read_text(encoding="utf-8")
    return [PlaybookEntry.model_validate(entry) for entry in json.loads(raw)]


def get_playbook_entry(entry_id: str) -> PlaybookEntry:
    for entry in load_playbook():
        if entry.id == entry_id:
            return entry
    raise KeyError(f"No playbook entry with id {entry_id!r}")


def render_price_band(entry: PlaybookEntry) -> str:
    """The one and only canonical price-band string for an entry.
    ProposalAgent is instructed to always use this (via a tool), never to
    format a band itself — the `price_floor` output guardrail rejects
    anything that doesn't match it exactly, so there is no room for the
    model to compute or interpolate a number (CLAUDE.md rule 4)."""

    return f"{entry.currency} {entry.price_band_low:,} - {entry.currency} {entry.price_band_high:,}"
