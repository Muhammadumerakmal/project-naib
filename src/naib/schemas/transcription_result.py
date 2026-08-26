from pydantic import BaseModel


class TranscriptionResult(BaseModel):
    """Output of transcribing one voicemail recording. `confidence` is
    derived from the STT provider's own per-segment signal (never invented)
    and is what routes a garbled/heavily-accented transcript to escalation
    instead of a false-confident qualification — see PLAN.md Phase 2.5."""

    text: str
    confidence: float
