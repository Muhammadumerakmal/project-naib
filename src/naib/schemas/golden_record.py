from typing import Literal

from pydantic import BaseModel


class GoldenRecord(BaseModel):
    """One labelled inbound message. See docs/EVALS.md § Golden set. The
    real 60-record set is `[YOU]` (PLAN.md Phase 2) — `golden_set.json`
    ships with a small, clearly-marked synthetic stand-in so the runner and
    its metrics are provably wired before real labels exist."""

    id: str
    is_synthetic: bool
    split: Literal["train", "held_out"]
    channel: str
    language: str
    raw_message: str
    label_qualified: bool
    label_band: str
    label_should_escalate: bool
    reason: str
