from naib.guardrails.proposal_guardrails import (
    capability_claim_check,
    no_commitment_check,
    price_floor_check,
    tone_and_length_check,
)
from naib.playbook import get_playbook_entry, render_price_band
from naib.schemas.proposal_draft import ProposalDraft

_ENTRY = get_playbook_entry("placeholder-website-basic")
_GOOD_DRAFT_MD = (
    "Hi Ali,\n\n"
    "Thanks for reaching out about a new website. Based on what you described, we'd build a "
    "5-page marketing site covering your services, one round of revisions included.\n\n"
    f"Investment: {render_price_band(_ENTRY)}.\n\n"
    "Best regards,\nNaib"
)


def _draft(**overrides: object) -> ProposalDraft:
    defaults = dict(
        playbook_entry_id=_ENTRY.id,
        price_band=render_price_band(_ENTRY),
        scope_summary="5-page marketing site",
        draft_md=_GOOD_DRAFT_MD,
        confidence=0.8,
        reasons=["Clear service match"],
    )
    defaults.update(overrides)
    return ProposalDraft(**defaults)  # type: ignore[arg-type]


def test_price_floor_passes_the_canonical_band() -> None:
    assert price_floor_check(_draft()) is None


def test_price_floor_trips_on_altered_band() -> None:
    reason = price_floor_check(_draft(price_band="PKR 500 - PKR 1000"))
    assert reason is not None
    assert "does not match playbook band" in reason


def test_price_floor_trips_on_unknown_entry() -> None:
    reason = price_floor_check(_draft(playbook_entry_id="does-not-exist"))
    assert reason is not None


def test_capability_claim_passes_a_clean_draft() -> None:
    assert capability_claim_check(_draft()) is None


def test_capability_claim_trips_on_foreign_capability() -> None:
    draft = _draft(
        draft_md=_GOOD_DRAFT_MD + "\nWe'll also handle payment-integration for you."
    )
    reason = capability_claim_check(draft)
    assert reason is not None
    assert "payment-integration" in reason


def test_no_commitment_passes_a_clean_draft() -> None:
    assert no_commitment_check(_draft()) is None


def test_no_commitment_trips_on_guarantee_language() -> None:
    draft = _draft(draft_md=_GOOD_DRAFT_MD + "\nWe guarantee delivery by March 3.")
    assert no_commitment_check(draft) is not None


def test_tone_and_length_passes_a_clean_draft() -> None:
    assert tone_and_length_check(_draft()) is None


def test_tone_and_length_trips_on_too_short_a_draft() -> None:
    reason = tone_and_length_check(_draft(draft_md="Hi, thanks, regards."))
    assert reason is not None
    assert "length" in reason


def test_tone_and_length_trips_on_missing_greeting() -> None:
    body = "We can build a 5-page site for you at the stated price. Thanks, regards." * 3
    reason = tone_and_length_check(_draft(draft_md=body))
    assert reason is not None
    assert "greeting" in reason


def test_tone_and_length_trips_on_em_dash_salad() -> None:
    draft = _draft(draft_md=_GOOD_DRAFT_MD + " — this — is — too — many — dashes —")
    reason = tone_and_length_check(draft)
    assert reason is not None
    assert "em-dash" in reason
