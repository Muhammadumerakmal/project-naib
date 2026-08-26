import httpx

from naib.api import _lifespan, app
from naib.store.db import get_sessionmaker
from naib.store.models import Client


async def test_webhook_enqueues_job_for_known_client_and_channel() -> None:
    async with get_sessionmaker()() as session:
        client = Client(name="API Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.post(
                "/webhooks/email",
                json={"client_id": str(client.id), "raw_text": "Hi, I need a website."},
            )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["lead_id"]


async def test_webhook_rejects_unknown_channel() -> None:
    async with get_sessionmaker()() as session:
        client = Client(name="API Test Agency 2", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.post(
                "/webhooks/carrier-pigeon",
                json={"client_id": str(client.id), "raw_text": "hi"},
            )

    assert response.status_code == 404


async def test_webhook_rejects_unknown_client() -> None:
    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.post(
                "/webhooks/email",
                json={"client_id": "00000000-0000-0000-0000-000000000000", "raw_text": "hi"},
            )

    assert response.status_code == 404


async def test_health() -> None:
    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
