import json
from pathlib import Path

from naib.defensibility_pack import generate_defensibility_pack
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead


async def _make_client() -> Client:
    async with get_sessionmaker()() as session:
        client = Client(name="Pack Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)
    return client


async def test_generate_defensibility_pack_writes_all_five_files_with_no_leads(
    tmp_path: Path,
) -> None:
    client = await _make_client()

    pack = await generate_defensibility_pack(client.id, tmp_path / "pack")

    names = {f.name for f in pack.files}
    assert names == {
        "architecture-summary.md",
        "eval-report.md",
        "sample-trace.json",
        "incident-runbook.md",
        "kill-switch.md",
    }
    for f in pack.files:
        assert f.exists()

    sample_trace = json.loads((tmp_path / "pack" / "sample-trace.json").read_text())
    assert "note" in sample_trace  # no leads yet -- honest placeholder, not a fabricated trace

    eval_report = (tmp_path / "pack" / "eval-report.md").read_text()
    assert "No golden-set eval run" in eval_report  # honest, not a fabricated number


async def test_generate_defensibility_pack_includes_a_real_signed_trace_when_a_lead_exists(
    tmp_path: Path,
) -> None:
    client = await _make_client()
    async with get_sessionmaker()() as session:
        lead = Lead(client_id=client.id, channel="email", raw_hash="pack-test")
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    await generate_defensibility_pack(client.id, tmp_path / "pack")

    sample_trace = json.loads((tmp_path / "pack" / "sample-trace.json").read_text())
    assert sample_trace["trace"]["lead_id"] == str(lead.id)
    assert "signature" in sample_trace
