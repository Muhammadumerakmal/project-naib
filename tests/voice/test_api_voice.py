import httpx
from sqlmodel import select

from naib.api import _lifespan, app
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead


async def _make_client() -> Client:
    async with get_sessionmaker()() as session:
        client = Client(name="Voice API Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)
    return client


async def test_voice_incoming_returns_twiml_with_static_greeting_and_record() -> None:
    client_row = await _make_client()

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.post(f"/webhooks/voice/{client_row.id}/incoming")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    body = response.text
    assert "<Say>" in body
    assert "<Record " in body
    assert f"/webhooks/voice/{client_row.id}/recording" in body


async def test_voice_incoming_unknown_client_returns_404() -> None:
    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.post(
                "/webhooks/voice/00000000-0000-0000-0000-000000000000/incoming"
            )

    assert response.status_code == 404


async def test_voice_recording_creates_lead_and_enqueues_job() -> None:
    client_row = await _make_client()

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.post(
                f"/webhooks/voice/{client_row.id}/recording",
                data={
                    "RecordingUrl": "https://api.twilio.com/fake.wav",
                    "CallSid": "CA1234567890",
                },
            )

    assert response.status_code == 200
    assert "<Say>" in response.text

    async with get_sessionmaker()() as session:
        leads = (
            await session.exec(select(Lead).where(Lead.client_id == client_row.id))
        ).all()

    assert len(leads) == 1
    assert leads[0].channel == "voice"
