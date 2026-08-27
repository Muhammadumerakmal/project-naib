"""Defensibility Pack generator -- docs/DEPLOYABILITY.md § 3: 'generated
per prospect: architecture summary, current eval report, sample trace
export, incident runbook, kill-switch documentation.' This assembles
already-existing artifacts into one per-prospect bundle; it invents
nothing new and never fabricates numbers -- an eval report with no data
says so plainly rather than making one up.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlmodel import select

from naib.evals.regression import load_previous_metrics
from naib.store.db import get_sessionmaker
from naib.store.models import Lead
from naib.trace_export import export_signed_trace

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ARCHITECTURE_SUMMARY_SOURCE = _REPO_ROOT / "docs" / "ARCHITECTURE.md"
_INCIDENT_RUNBOOK_SOURCE = _REPO_ROOT / "docs" / "INCIDENT_RUNBOOK.md"

_KILL_SWITCH_DOC = """# Kill switch

One control, on the client dashboard, that halts every run for this account instantly.

- `POST /clients/{client_id}/kill-switch {"enabled": true}` -- or the button on the dashboard,
  built for a non-technical person to find and use unaided (PLAN.md Phase 7 gate).
- A queued job that hasn't started yet never starts once the switch is on
  (`naib.worker._kill_switch_active`, checked at the top of every job entry point: `process_lead`,
  `process_voice_lead`, `process_followup`).
- Exercised through the real job queue (not just a direct function call) in
  `tests/test_worker_integration.py`, so this is proven against arq + Redis dispatch, not only
  the function body in isolation.
- See `docs/INCIDENT_RUNBOOK.md` step 1 for exactly when and how to use it.
"""


@dataclass
class DefensibilityPack:
    output_dir: Path
    files: list[Path]


async def _pick_sample_lead(client_id: uuid.UUID) -> uuid.UUID | None:
    async with get_sessionmaker()() as session:
        lead = (
            await session.exec(
                select(Lead)
                .where(Lead.client_id == client_id)
                .order_by(Lead.created_at.desc())  # type: ignore[attr-defined]
            )
        ).first()
    return lead.id if lead else None


def _render_eval_report() -> str:
    metrics = load_previous_metrics()
    if metrics is None:
        return (
            "# Current eval report\n\n"
            "No golden-set eval run has been recorded yet. Run `uv run pytest -m eval` "
            "and `naib.evals.regression.save_metrics` before sending this pack to a "
            "prospect who will ask for numbers -- do not paste in a number from memory.\n"
        )
    lines = ["# Current eval report", "", "| Metric | Value |", "|---|---|"]
    for name, value in metrics.items():
        lines.append(f"| {name} | {value:.1%} |")
    return "\n".join(lines) + "\n"


async def _render_sample_trace(client_id: uuid.UUID) -> str:
    lead_id = await _pick_sample_lead(client_id)
    if lead_id is None:
        return json.dumps(
            {
                "note": (
                    "No leads recorded yet for this client -- run one through the "
                    "pipeline (or naib.cli replay) before sending this pack."
                )
            },
            indent=2,
        )
    bundle = await export_signed_trace(lead_id)
    return json.dumps(bundle, indent=2, default=str)


def _write_pack_files(output_dir: Path, *, eval_report: str, sample_trace: str) -> list[Path]:
    """All blocking file I/O for the pack -- reads of the static docs it
    copies in, and every write -- lives here so it can run in one thread
    (ruff ASYNC240: no pathlib calls directly inside an async function)."""

    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "architecture-summary.md": _ARCHITECTURE_SUMMARY_SOURCE.read_text(encoding="utf-8"),
        "eval-report.md": eval_report,
        "sample-trace.json": sample_trace,
        "incident-runbook.md": _INCIDENT_RUNBOOK_SOURCE.read_text(encoding="utf-8"),
        "kill-switch.md": _KILL_SWITCH_DOC,
    }
    written: list[Path] = []
    for filename, content in files.items():
        dest = output_dir / filename
        dest.write_text(content, encoding="utf-8")
        written.append(dest)
    return written


async def generate_defensibility_pack(
    client_id: uuid.UUID, output_dir: Path
) -> DefensibilityPack:
    # Only the DB read + trace export need to be awaited.
    sample_trace = await _render_sample_trace(client_id)
    eval_report = _render_eval_report()  # sync, but no pathlib call of its own

    written = await asyncio.to_thread(
        _write_pack_files, output_dir, eval_report=eval_report, sample_trace=sample_trace
    )

    return DefensibilityPack(output_dir=output_dir, files=written)
