import uuid

import httpx

from naib.api import _lifespan, app
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead


def _auth(client: Client) -> dict[str, str]:
    return {"Authorization": f"Bearer {client.dashboard_token}"}


async def _make_client_and_lead() -> tuple[Client, Lead]:
    async with get_sessionmaker()() as session:
        client = Client(name="Trace API Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="email", raw_hash=str(uuid.uuid4()))
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
    return client, lead


async def test_lead_trace_endpoint_returns_a_signed_bundle() -> None:
    client, lead = await _make_client_and_lead()

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get(f"/leads/{lead.id}/trace", headers=_auth(client))

    assert response.status_code == 200
    body = response.json()
    assert body["trace"]["lead_id"] == str(lead.id)
    assert "signature" in body


async def test_lead_trace_endpoint_404s_for_unknown_lead() -> None:
    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get(
                f"/leads/{uuid.uuid4()}/trace", headers={"Authorization": "Bearer whatever"}
            )

    assert response.status_code == 404


async def test_lead_trace_endpoint_rejects_a_missing_token() -> None:
    _client, lead = await _make_client_and_lead()

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get(f"/leads/{lead.id}/trace")

    assert response.status_code == 401


async def test_lead_trace_endpoint_rejects_another_clients_token() -> None:
    _client, lead = await _make_client_and_lead()
    other_client, _other_lead = await _make_client_and_lead()

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get(
                f"/leads/{lead.id}/trace", headers=_auth(other_client)
            )

    assert response.status_code == 401
