"""FastAPI webhook layer. Handlers only validate and enqueue — the pipeline
itself runs in the arq worker (`naib.worker`), which is also where a
guardrail tripwire is caught per CLAUDE.md rule ('Tripwires raise. Catch
InputGuardrailTripwireTriggered at the API boundary'). See
docs/ARCHITECTURE.md § Runtime shape.
"""

import hashlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import select

from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead
from naib.trace_export import export_signed_trace

# Static, non-AI prompts — Twilio's <Say> is text-to-speech reading a fixed
# script, not a generated response. See PLAN.md Phase 2.5: "no AI speaks."
_VOICE_GREETING = (
    "Thanks for calling. Please leave your name, your business, and what you "
    "need after the tone."
)
_VOICE_FAREWELL = "Thanks, we've got your message and will be in touch soon."

_SUPPORTED_CHANNELS = {"email", "whatsapp", "form", "voice"}


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    yield
    await app.state.arq_pool.aclose()


app = FastAPI(title="Naib", lifespan=_lifespan)


class InboundMessage(BaseModel):
    client_id: uuid.UUID
    raw_text: str


class InboundAccepted(BaseModel):
    lead_id: uuid.UUID
    status: str = "queued"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhooks/{channel}", status_code=202)
async def inbound_webhook(channel: str, message: InboundMessage) -> InboundAccepted:
    if channel not in _SUPPORTED_CHANNELS:
        raise HTTPException(status_code=404, detail=f"unknown channel: {channel}")

    async with get_sessionmaker()() as session:
        client = (
            await session.exec(select(Client).where(Client.id == message.client_id))
        ).first()
        if client is None:
            raise HTTPException(status_code=404, detail="unknown client_id")

        raw_hash = hashlib.sha256(message.raw_text.encode("utf-8")).hexdigest()
        lead = Lead(client_id=message.client_id, channel=channel, raw_hash=raw_hash)
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    arq_pool: ArqRedis = app.state.arq_pool
    await arq_pool.enqueue_job(
        "process_lead",
        str(lead.id),
        str(message.client_id),
        message.raw_text,
        channel,
    )

    return InboundAccepted(lead_id=lead.id)


@app.post("/webhooks/voice/{client_id}/incoming")
async def voice_incoming(client_id: uuid.UUID) -> Response:
    """Twilio Voice webhook for a new call. Answers with a static greeting
    and records the message — no AI-generated speech, no live conversation.
    See PLAN.md Phase 2.5."""

    async with get_sessionmaker()() as session:
        client = (await session.exec(select(Client).where(Client.id == client_id))).first()
        if client is None:
            raise HTTPException(status_code=404, detail="unknown client_id")

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Say>{_VOICE_GREETING}</Say>"
        f'<Record action="/webhooks/voice/{client_id}/recording" '
        'method="POST" maxLength="120" playBeep="true" />'
        "<Hangup/>"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@app.post("/webhooks/voice/{client_id}/recording")
async def voice_recording(
    client_id: uuid.UUID,
    RecordingUrl: str = Form(...),  # noqa: N803  (Twilio's field name, not ours)
    CallSid: str = Form(...),  # noqa: N803
) -> Response:
    """Twilio's callback once a recording is ready. Enqueues transcription +
    the (unmodified) Intake -> Qualifier pipeline; never processes audio
    inline in the request handler."""

    async with get_sessionmaker()() as session:
        client = (await session.exec(select(Client).where(Client.id == client_id))).first()
        if client is None:
            raise HTTPException(status_code=404, detail="unknown client_id")

        raw_hash = hashlib.sha256(f"{CallSid}:{RecordingUrl}".encode()).hexdigest()
        lead = Lead(client_id=client_id, channel="voice", raw_hash=raw_hash)
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    arq_pool: ArqRedis = app.state.arq_pool
    await arq_pool.enqueue_job(
        "process_voice_lead",
        str(lead.id),
        str(client_id),
        RecordingUrl,
    )

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Say>{_VOICE_FAREWELL}</Say><Hangup/></Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@app.get("/leads/{lead_id}/trace")
async def lead_trace(lead_id: uuid.UUID) -> dict[str, object]:
    """Signed JSON trace bundle for one lead — PLAN.md Phase 6, CLAUDE.md
    rule 3: 'if a client asks why did it say that, we answer with a
    record.' Verify with naib.trace_export.verify_trace."""

    async with get_sessionmaker()() as session:
        lead = (await session.exec(select(Lead).where(Lead.id == lead_id))).first()
        if lead is None:
            raise HTTPException(status_code=404, detail="unknown lead_id")

    return await export_signed_trace(lead_id)
