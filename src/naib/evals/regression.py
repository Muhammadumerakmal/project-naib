"""Golden-set regression tracking (docs/EVALS.md ship gate: 'no golden
metric regressed more than 2 points versus main', PLAN.md Phase 6). Results
are written to a local JSON file after a real `-m eval` run; the next run
compares against it. Not wired into CI (golden-set evals cost money and
aren't run there by default — see pyproject.toml's addopts) — this is the
mechanism `/ship-check` calls when a human runs it with real credentials.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from naib.evals.golden_set import GoldenSetMetrics

DEFAULT_RESULTS_PATH = Path("eval-results/golden_set_latest.json")
REGRESSION_THRESHOLD_POINTS = 0.02  # docs/EVALS.md: "no metric regressed >2pts"

_TRACKED_METRICS = ("qualification_agreement", "escalation_recall", "escalation_precision")


@dataclass
class Regression:
    metric: str
    previous: float
    current: float

    @property
    def dropped_points(self) -> float:
        return self.previous - self.current


def save_metrics(metrics: GoldenSetMetrics, *, path: Path = DEFAULT_RESULTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "recorded_at": datetime.now(UTC).isoformat(),
        **{m: getattr(metrics, m) for m in _TRACKED_METRICS},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_previous_metrics(*, path: Path = DEFAULT_RESULTS_PATH) -> dict[str, float] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {m: data[m] for m in _TRACKED_METRICS if m in data}


def find_regressions(
    metrics: GoldenSetMetrics, *, path: Path = DEFAULT_RESULTS_PATH
) -> list[Regression]:
    previous = load_previous_metrics(path=path)
    if previous is None:
        return []

    regressions: list[Regression] = []
    for metric in _TRACKED_METRICS:
        prev_value = previous.get(metric)
        if prev_value is None:
            continue
        current_value = getattr(metrics, metric)
        if prev_value - current_value > REGRESSION_THRESHOLD_POINTS:
            regressions.append(
                Regression(metric=metric, previous=prev_value, current=current_value)
            )
    return regressions
