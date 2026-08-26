import uuid

import httpx

from naib.api import _lifespan, app
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead


async def test_lead_trace_endpoint_returns_a_signed_bundle() -> None:
    async with get_sessionmaker()() as session:
        client = Client(name="Trace API Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="email", raw_hash=str(uuid.uuid4()))
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get(f"/leads/{lead.id}/trace")

    assert response.status_code == 200
    body = response.json()
    assert body["trace"]["lead_id"] == str(lead.id)
    assert "signature" in body


async def test_lead_trace_endpoint_404s_for_unknown_lead() -> None:
    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get(
                f"/leads/{uuid.uuid4()}/trace"
            )

    assert response.status_code == 404
