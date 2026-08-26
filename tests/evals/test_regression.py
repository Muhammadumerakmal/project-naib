from pathlib import Path

import pytest

from naib.evals.golden_set import GoldenSetMetrics
from naib.evals.regression import find_regressions, load_previous_metrics, save_metrics


def _metrics(**overrides: float) -> GoldenSetMetrics:
    defaults = dict(qualification_agreement=0.9, escalation_recall=0.95, escalation_precision=0.85)
    defaults.update(overrides)
    return GoldenSetMetrics(total=10, **defaults)  # type: ignore[arg-type]


def test_find_regressions_is_empty_with_no_prior_results(tmp_path: Path) -> None:
    path = tmp_path / "golden_set_latest.json"
    assert find_regressions(_metrics(), path=path) == []


def test_save_and_load_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "golden_set_latest.json"
    save_metrics(_metrics(qualification_agreement=0.9), path=path)

    loaded = load_previous_metrics(path=path)

    assert loaded is not None
    assert loaded["qualification_agreement"] == 0.9


def test_find_regressions_flags_a_drop_beyond_the_threshold(tmp_path: Path) -> None:
    path = tmp_path / "golden_set_latest.json"
    save_metrics(_metrics(qualification_agreement=0.90), path=path)

    regressions = find_regressions(_metrics(qualification_agreement=0.80), path=path)

    assert len(regressions) == 1
    assert regressions[0].metric == "qualification_agreement"
    assert regressions[0].dropped_points == pytest.approx(0.10)


def test_find_regressions_ignores_a_small_drop_within_threshold(tmp_path: Path) -> None:
    path = tmp_path / "golden_set_latest.json"
    save_metrics(_metrics(qualification_agreement=0.90), path=path)

    regressions = find_regressions(_metrics(qualification_agreement=0.885), path=path)

    assert regressions == []
