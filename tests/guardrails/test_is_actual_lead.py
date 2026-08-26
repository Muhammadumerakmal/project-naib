from naib.guardrails.is_actual_lead import looks_like_non_lead


def test_flags_newsletter_unsubscribe() -> None:
    matched = looks_like_non_lead(
        "Thanks for subscribing! Click here to unsubscribe. View this in your browser."
    )
    assert matched


def test_flags_invoice_notification() -> None:
    matched = looks_like_non_lead("This is an automated notification: Invoice #48213 is due.")
    assert matched


def test_does_not_flag_genuine_inquiry() -> None:
    matched = looks_like_non_lead(
        "Hi, I run a small clinic and need a 5-page website. Budget around PKR 80,000."
    )
    assert matched == []
