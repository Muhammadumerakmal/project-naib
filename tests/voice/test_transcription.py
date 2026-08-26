from naib.voice.transcription import _confidence_from_segments


def test_confidence_from_segments_is_zero_for_no_segments() -> None:
    assert _confidence_from_segments([]) == 0.0


def test_confidence_from_segments_is_high_for_clean_speech() -> None:
    confidence = _confidence_from_segments(
        [
            {"avg_logprob": -0.1, "no_speech_prob": 0.01},
            {"avg_logprob": -0.05, "no_speech_prob": 0.02},
        ]
    )
    assert confidence > 0.85


def test_confidence_from_segments_is_low_for_garbled_speech() -> None:
    confidence = _confidence_from_segments(
        [{"avg_logprob": -2.5, "no_speech_prob": 0.7}, {"avg_logprob": -3.0, "no_speech_prob": 0.8}]
    )
    assert confidence < 0.2


def test_confidence_from_segments_is_clamped_to_zero_one() -> None:
    confidence = _confidence_from_segments([{"avg_logprob": 5.0, "no_speech_prob": -1.0}])
    assert 0.0 <= confidence <= 1.0
