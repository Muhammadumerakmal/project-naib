from naib.guardrails.language_route import detect_language


def test_detects_english() -> None:
    language, confidence = detect_language("Hi, I need a 5-page website for my clinic.")
    assert language == "en"
    assert confidence > 0.5


def test_detects_urdu_script() -> None:
    language, confidence = detect_language("مجھے ایک ویب سائٹ چاہیے")
    assert language == "ur"
    assert confidence > 0.9


def test_detects_roman_urdu() -> None:
    language, confidence = detect_language(
        "assalam sir, mujhe ek website bnwani hai, price kitna hoga aap ka"
    )
    assert language == "roman-ur"
    assert confidence > 0.5


def test_empty_text_defaults_to_english() -> None:
    language, _confidence = detect_language("")
    assert language == "en"
