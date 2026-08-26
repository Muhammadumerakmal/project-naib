"""End-to-end voice pipeline test against real Postgres, with a fake
Transcriber (no OpenAI/Twilio calls) and both agents' models swapped for
ScriptedModel, same pattern as tests/agents/test_pipeline.py.
"""

import json

import pytest
from agents.testing import ScriptedModel, assistant_message, function_call
from sqlmodel import select

from naib.agents import pipeline as pipeline_module
from naib.agents.intake import build_intake_agent
from naib.agents.qualifier import build_qualifier_agent
from naib.icp import DEFAULT_ICP_CONFIG
from naib.schemas.transcription_result import TranscriptionResult
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, Lead
from naib.voice.pipeline import run_voice_pipeline

_NORMALIZED_LEAD_ARGS = {
    "channel": "voice",
    "contact_name": "Bilal",
    "contact_email": None,
    "contact_phone": "03001234567",
    "company_name": "Bilal Traders",
    "message_summary": "Wants a catalog website.",
    "requested_service": "website",
    "budget_signal": None,
    "language": "en",
    "raw_hash": "voice-test",
    "confidence": 0.9,
    "reasons": ["Clear service request"],
}


class _FakeTranscriber:
    def __init__(self, *, text: str, confidence: float) -> None:
        self._text = text
        self._confidence = confidence

    async def transcribe(self, recording_url: str) -> TranscriptionResult:
        return TranscriptionResult(text=self._text, confidence=self._confidence)


def _wire_scripted_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    def _build_qualifier(
        icp_config: object, enrichment_agent: object, retrieval_agent: object
    ) -> object:
        agent = build_qualifier_agent(
            DEFAULT_ICP_CONFIG, enrichment_agent, retrieval_agent  # type: ignore[arg-type]
        )
        agent.model = ScriptedModel(
            [
                [
                    assistant_message(
                        json.dumps(
                            {
                                "qualified": True,
                                "score": 0.7,
                                "band": "medium",
                                "disqualifiers": [],
                                "should_escalate": False,
                                "confidence": 0.8,
                                "reasons": ["Clear service request"],
                            }
                        )
                    )
                ]
            ]
        )
        return agent

    def _build_intake(qualifier_agent: object) -> object:
        agent = build_intake_agent(qualifier_agent)  # type: ignore[arg-type]
        handoff_tool_name = agent.handoffs[0].tool_name
        agent.model = ScriptedModel(
            [[function_call(handoff_tool_name, _NORMALIZED_LEAD_ARGS, call_id="call-1")]]
        )
        return agent

    monkeypatch.setattr(pipeline_module, "build_qualifier_agent", _build_qualifier)
    monkeypatch.setattr(pipeline_module, "build_intake_agent", _build_intake)


async def _make_client_and_lead(raw_hash: str) -> tuple[Client, Lead]:
    async with get_sessionmaker()() as session:
        client = Client(name="Voice Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="voice", raw_hash=raw_hash)
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
    return client, lead


async def test_voice_pipeline_persists_lead_with_voice_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_scripted_pipeline(monkeypatch)
    client, lead = await _make_client_and_lead("voice-happy-path")

    result = await run_voice_pipeline(
        lead_id=lead.id,
        client=client,
        recording_url="https://api.twilio.com/fake-recording.wav",
        transcriber=_FakeTranscriber(
            text="Hi, I run a shop and want a catalog website.", confidence=0.95
        ),
    )

    assert result.qualified is True

    async with get_sessionmaker()() as session:
        refreshed = (await session.exec(select(Lead).where(Lead.id == lead.id))).one()

    assert refreshed.channel == "voice"
    assert refreshed.status == "qualified"


async def test_low_stt_confidence_forces_escalation(monkeypatch: pytest.MonkeyPatch) -> None:
    """PLAN.md Phase 2.5 gate: a deliberately garbled/low-confidence
    transcript must route to escalation rather than a false-confident
    qualification, even though the (scripted) qualifier itself said
    qualified=True with no escalation."""

    _wire_scripted_pipeline(monkeypatch)
    client, lead = await _make_client_and_lead("voice-garbled")

    await run_voice_pipeline(
        lead_id=lead.id,
        client=client,
        recording_url="https://api.twilio.com/fake-garbled.wav",
        transcriber=_FakeTranscriber(text="mmph ... static ... website maybe", confidence=0.1),
    )

    async with get_sessionmaker()() as session:
        refreshed = (await session.exec(select(Lead).where(Lead.id == lead.id))).one()
        escalations = (
            await session.exec(select(Escalation).where(Escalation.lead_id == lead.id))
        ).all()

    assert refreshed.status == "needs_escalation"
    assert len(escalations) == 1
    assert escalations[0].reason == "low_transcription_confidence"


async def test_high_stt_confidence_does_not_force_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _wire_scripted_pipeline(monkeypatch)
    client, lead = await _make_client_and_lead("voice-clean")

    await run_voice_pipeline(
        lead_id=lead.id,
        client=client,
        recording_url="https://api.twilio.com/fake-clean.wav",
        transcriber=_FakeTranscriber(text="Hi, I need a website for my shop.", confidence=0.95),
    )

    async with get_sessionmaker()() as session:
        refreshed = (await session.exec(select(Lead).where(Lead.id == lead.id))).one()
        escalations = (
            await session.exec(select(Escalation).where(Escalation.lead_id == lead.id))
        ).all()

    assert refreshed.status != "needs_escalation"
    assert escalations == []
