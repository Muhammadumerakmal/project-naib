"""Voicemail transcription. `Transcriber` is a Protocol so the pipeline
never depends on a concrete provider — tests use a fake, production uses
`OpenAIWhisperTranscriber`. Judgment call: this module's real-provider path
(downloading a Twilio recording, calling OpenAI's transcription endpoint) is
correctly coded against both APIs' documented shapes but has not been
exercised against live Twilio/OpenAI credentials — flagged the same way the
Phase 2 golden set's real numbers are flagged as pending. See PLAN.md
Phase 2.5.
"""

import math
from typing import Protocol

import httpx
from openai import AsyncOpenAI

from naib.schemas.transcription_result import TranscriptionResult
from naib.settings import get_settings


class Transcriber(Protocol):
    async def transcribe(self, recording_url: str) -> TranscriptionResult: ...


def _confidence_from_segments(segments: list[dict[str, float]]) -> float:
    """Derive a 0-1 confidence from Whisper's verbose_json per-segment
    signal: high average log-probability and low no-speech probability both
    push confidence up. No segments (silent/empty recording) means zero
    confidence, not an invented default."""

    if not segments:
        return 0.0

    scores = [
        max(0.0, min(1.0, math.exp(segment["avg_logprob"]) * (1 - segment["no_speech_prob"])))
        for segment in segments
    ]
    return sum(scores) / len(scores)


class OpenAIWhisperTranscriber:
    """Downloads the recording from Twilio (HTTP Basic Auth with the
    account SID/auth token) and transcribes it with OpenAI's Whisper model
    in verbose_json mode, so per-segment confidence is available."""

    def __init__(self) -> None:
        settings = get_settings()
        self._twilio_account_sid = settings.twilio_account_sid
        self._twilio_auth_token = settings.twilio_auth_token
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=get_settings().openai_api_key)
        return self._client

    async def transcribe(self, recording_url: str) -> TranscriptionResult:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(
                recording_url,
                auth=(self._twilio_account_sid, self._twilio_auth_token),
                follow_redirects=True,
            )
            response.raise_for_status()
            audio_bytes = response.content

        transcription = await self._get_client().audio.transcriptions.create(
            file=("recording.wav", audio_bytes),
            model="whisper-1",
            response_format="verbose_json",
        )

        segments = [
            {"avg_logprob": s.avg_logprob, "no_speech_prob": s.no_speech_prob}
            for s in (transcription.segments or [])
        ]
        return TranscriptionResult(
            text=transcription.text, confidence=_confidence_from_segments(segments)
        )
