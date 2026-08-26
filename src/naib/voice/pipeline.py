"""Voice pipeline: transcribe, then rejoin the unmodified Intake -> Qualifier
pipeline from Phase 2. STT confidence is folded in afterward so a garbled or
heavily-accented transcript degrades gracefully into escalation rather than
a false-confident qualification — see PLAN.md Phase 2.5.
"""

import uuid

from sqlmodel import select

from naib.agents.pipeline import run_intake_qualifier
from naib.events import record_event
from naib.schemas.qualification_result import QualificationResult
from naib.schemas.transcription_result import TranscriptionResult
from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Escalation, Lead
from naib.voice.transcription import Transcriber


async def run_voice_pipeline(
    *,
    lead_id: uuid.UUID,
    client: Client,
    recording_url: str,
    transcriber: Transcriber,
) -> QualificationResult:
    transcription = await transcriber.transcribe(recording_url)

    await record_event(
        run_id=uuid.uuid4(),
        agent="VoicePipeline",
        event_type="transcription",
        lead_id=lead_id,
        outcome="success",
        payload={"recording_url": recording_url, "stt_confidence": transcription.confidence},
    )

    qualification = await run_intake_qualifier(
        lead_id=lead_id, client=client, raw_text=transcription.text, channel="voice"
    )

    await _fold_stt_confidence(lead_id, transcription)

    return qualification


async def _fold_stt_confidence(lead_id: uuid.UUID, transcription: TranscriptionResult) -> None:
    settings = get_settings()
    async with get_sessionmaker()() as session:
        lead = (await session.exec(select(Lead).where(Lead.id == lead_id))).one()

        if lead.normalized is not None:
            existing_confidence = lead.normalized.get("confidence", 1.0)
            lead.normalized = {
                **lead.normalized,
                "confidence": min(existing_confidence, transcription.confidence),
            }
        prior_confidence = lead.confidence if lead.confidence is not None else 1.0
        lead.confidence = min(prior_confidence, transcription.confidence)

        if transcription.confidence < settings.escalate_below:
            lead.status = "needs_escalation"
            session.add(
                Escalation(
                    lead_id=lead_id,
                    reason="low_transcription_confidence",
                    brief_md=(
                        "# Escalation — low transcription confidence\n\n"
                        f"Speech-to-text confidence was {transcription.confidence:.2f} "
                        f"(threshold {settings.escalate_below}). The transcript may be "
                        "unreliable — listen to the original recording rather than trust "
                        "this qualification."
                    ),
                )
            )

        session.add(lead)
        await session.commit()
