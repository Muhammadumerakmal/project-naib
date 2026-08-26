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
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead

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
