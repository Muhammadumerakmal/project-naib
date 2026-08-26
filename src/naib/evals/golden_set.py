"""Golden-set loader and agreement-metric runner. See docs/EVALS.md § Golden
set for the metrics and thresholds this exists to prove. Runs real agents
against a real model (no ScriptedModel) — this is the `-m eval` suite,
"slow, costs money" (CLAUDE.md commands), never run by default `pytest` or
by CI's unit step (see the addopts default marker exclusion in
pyproject.toml).
"""

import importlib.resources
import json
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from agents import InputGuardrailTripwireTriggered, Runner

from naib.agents.context import NaibContext
from naib.agents.intake import build_intake_agent
from naib.agents.qualifier import build_qualifier_agent
from naib.guardrails.injection import wrap_untrusted
from naib.icp import load_icp_config
from naib.schemas.golden_record import GoldenRecord
from naib.schemas.qualification_result import QualificationResult
from naib.store.models import Client


@lru_cache
def load_golden_set(split: Literal["train", "held_out"] | None = None) -> tuple[GoldenRecord, ...]:
    raw = importlib.resources.files("naib.data").joinpath("golden_set.json").read_text("utf-8")
    records = [GoldenRecord.model_validate(item) for item in json.loads(raw)]
    if split is not None:
        records = [r for r in records if r.split == split]
    return tuple(records)


@dataclass
class Disagreement:
    record_id: str
    predicted_qualified: bool
    label_qualified: bool
    reason: str


@dataclass
class GoldenSetMetrics:
    total: int
    qualification_agreement: float
    escalation_recall: float
    escalation_precision: float
    disagreements: list[Disagreement] = field(default_factory=list)


async def run_golden_set(records: tuple[GoldenRecord, ...], client: Client) -> GoldenSetMetrics:
    qualifier_agent = build_qualifier_agent(load_icp_config(client.icp_config))
    intake_agent = build_intake_agent(qualifier_agent)

    correct_qualification = 0
    actual_escalations = 0
    escalations_caught = 0
    predicted_escalations = 0
    correct_escalation_predictions = 0
    disagreements: list[Disagreement] = []

    for record in records:
        context = NaibContext(client=client, lead_id=uuid.uuid4(), language=record.language)
        wrapped = wrap_untrusted(record.raw_message, source=record.channel)

        predicted_qualified = False
        predicted_escalate = False
        try:
            result = await Runner.run(intake_agent, wrapped, context=context)
            if isinstance(result.final_output, QualificationResult):
                predicted_qualified = result.final_output.qualified
                predicted_escalate = result.final_output.should_escalate
        except InputGuardrailTripwireTriggered:
            # A tripwire is itself a form of escalation — the message never
            # reached a qualification decision, a human must read it.
            predicted_escalate = True

        if predicted_qualified == record.label_qualified:
            correct_qualification += 1
        else:
            disagreements.append(
                Disagreement(
                    record_id=record.id,
                    predicted_qualified=predicted_qualified,
                    label_qualified=record.label_qualified,
                    reason=record.reason,
                )
            )

        if record.label_should_escalate:
            actual_escalations += 1
            if predicted_escalate:
                escalations_caught += 1
        if predicted_escalate:
            predicted_escalations += 1
            if record.label_should_escalate:
                correct_escalation_predictions += 1

    total = len(records)
    return GoldenSetMetrics(
        total=total,
        qualification_agreement=correct_qualification / total if total else 0.0,
        escalation_recall=(escalations_caught / actual_escalations) if actual_escalations else 1.0,
        escalation_precision=(
            correct_escalation_predictions / predicted_escalations if predicted_escalations else 1.0
        ),
        disagreements=disagreements,
    )
