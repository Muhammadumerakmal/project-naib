from naib.guardrails.pii import redact_pii


def test_redacts_cnic() -> None:
    text, found = redact_pii("My CNIC is 42101-1234567-1, please proceed.")
    assert "42101-1234567-1" not in text
    assert "[REDACTED-CNIC]" in text
    assert "cnic" in found


def test_redacts_card_number() -> None:
    text, found = redact_pii("Card: 4111111111111111 exp 12/28")
    assert "4111111111111111" not in text
    assert "card" in found


def test_leaves_clean_text_untouched() -> None:
    text, found = redact_pii("I need a website for my clinic, budget 50k PKR.")
    assert text == "I need a website for my clinic, budget 50k PKR."
    assert found == []


def test_does_not_flag_short_phone_number() -> None:
    _text, found = redact_pii("Call me on 03001234567.")
    assert "card" not in found
