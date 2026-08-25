import pytest

from naib.settings import Settings


def test_defaults_match_env_example() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.model_fast == "gpt-4.1-mini"
    assert settings.model_strong == "gpt-4.1"
    assert settings.autonomy_level == "draft_only"
    assert settings.kill_switch is False


@pytest.mark.parametrize(
    ("env_var", "value", "attr", "expected"),
    [
        ("NAIB_MODEL_FAST", "gpt-5-nano", "model_fast", "gpt-5-nano"),
        ("DATABASE_URL", "postgresql+asyncpg://x:y@z:5432/w", "database_url", "postgresql+asyncpg://x:y@z:5432/w"),
        ("NAIB_QUALIFY_CONFIDENCE_MIN", "0.9", "qualify_confidence_min", 0.9),
        ("NAIB_KILL_SWITCH", "true", "kill_switch", True),
    ],
)
def test_env_vars_map_to_expected_fields(
    monkeypatch: pytest.MonkeyPatch, env_var: str, value: str, attr: str, expected: object
) -> None:
    monkeypatch.setenv(env_var, value)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert getattr(settings, attr) == expected


def test_prefixed_field_ignores_unprefixed_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """model_fast reads NAIB_MODEL_FAST, not MODEL_FAST — the aliasing must
    not silently fall back to a name collision."""

    monkeypatch.setenv("MODEL_FAST", "should-not-apply")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.model_fast == "gpt-4.1-mini"
