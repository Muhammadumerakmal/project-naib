import pytest

from naib.playbook import get_playbook_entry, load_playbook


def test_playbook_loads_and_validates_against_schema() -> None:
    entries = load_playbook()

    assert len(entries) > 0
    for entry in entries:
        assert entry.price_band_low <= entry.price_band_high
        assert entry.currency == "PKR"


def test_playbook_entries_are_clearly_labelled_placeholders() -> None:
    """This is expected to start failing the moment Umer's real playbook
    (PLAN.md Phase 1 [YOU]) replaces naib/data/playbook.json — that's the
    signal to update this test and the Phase 4 is_placeholder guardrail
    alongside it, not a bug."""

    entries = load_playbook()

    assert all(entry.is_placeholder for entry in entries)


def test_get_playbook_entry_looks_up_by_id() -> None:
    first = load_playbook()[0]

    assert get_playbook_entry(first.id) == first


def test_get_playbook_entry_raises_for_unknown_id() -> None:
    with pytest.raises(KeyError):
        get_playbook_entry("does-not-exist")
