import uuid

import httpx

from naib.api import _lifespan, app
from naib.approvals import request_approval
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead, Proposal


def _auth(client: Client) -> dict[str, str]:
    return {"Authorization": f"Bearer {client.dashboard_token}"}


async def _make_client_lead_and_proposal() -> tuple[Client, Lead, Proposal]:
    async with get_sessionmaker()() as session:
        client = Client(name="Dashboard API Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(client_id=client.id, channel="email", raw_hash=str(uuid.uuid4()))
        session.add(lead)
        await session.commit()
        await session.refresh(lead)

        proposal = Proposal(
            lead_id=lead.id,
            playbook_entry_id="placeholder-website-basic",
            price_band="PKR 0 - PKR 99,999",
            draft_md="Hi, here is our proposal...",
        )
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)

    return client, lead, proposal


async def test_get_client_detail_and_toggle_kill_switch() -> None:
    client, _lead, _proposal = await _make_client_lead_and_proposal()

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            detail = await http_client.get(f"/clients/{client.id}", headers=_auth(client))
            assert detail.status_code == 200
            assert detail.json()["kill_switch"] is False

            toggled = await http_client.post(
                f"/clients/{client.id}/kill-switch",
                json={"enabled": True},
                headers=_auth(client),
            )

    assert toggled.status_code == 200
    assert toggled.json()["kill_switch"] is True


async def test_list_approvals_and_decide_via_api() -> None:
    client, lead, proposal = await _make_client_lead_and_proposal()
    approval = await request_approval(
        entity_type="proposal", entity_id=proposal.id, action="commit_price"
    )

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            listed = await http_client.get(
                f"/clients/{client.id}/approvals", headers=_auth(client)
            )
            assert listed.status_code == 200
            assert len(listed.json()) == 1
            assert listed.json()[0]["lead_id"] == str(lead.id)

            decided = await http_client.post(
                f"/approvals/{approval.id}/decide",
                json={"decided_by": "umer@example.com", "decision": "approved"},
                headers=_auth(client),
            )
            assert decided.status_code == 200

            after = await http_client.get(
                f"/clients/{client.id}/approvals",
                params={"pending_only": True},
                headers=_auth(client),
            )

    assert after.json() == []


async def test_get_client_autonomy_via_api() -> None:
    client, _lead, _proposal = await _make_client_lead_and_proposal()

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get(
                f"/clients/{client.id}/autonomy", headers=_auth(client)
            )

    assert response.status_code == 200
    body = response.json()
    actions = {row["action"] for row in body}
    assert actions == {"commit_price", "send_followup"}
    assert all(row["eligible"] is False for row in body)


async def test_get_client_metrics_via_api() -> None:
    client, _lead, _proposal = await _make_client_lead_and_proposal()

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get(
                f"/clients/{client.id}/metrics", headers=_auth(client)
            )

    assert response.status_code == 200
    body = response.json()
    assert "edit_rate_over_time" in body
    assert "injections_blocked_total" in body


async def test_dashboard_routes_reject_a_missing_token() -> None:
    client, _lead, _proposal = await _make_client_lead_and_proposal()

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get(f"/clients/{client.id}")

    assert response.status_code == 401


async def test_dashboard_routes_reject_another_clients_token() -> None:
    client, _lead, _proposal = await _make_client_lead_and_proposal()
    other_client, _other_lead, _other_proposal = await _make_client_lead_and_proposal()

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.get(
                f"/clients/{client.id}", headers=_auth(other_client)
            )

    assert response.status_code == 401


async def test_decide_approval_rejects_wrong_client_token() -> None:
    client, _lead, proposal = await _make_client_lead_and_proposal()
    other_client, _other_lead, _other_proposal = await _make_client_lead_and_proposal()
    approval = await request_approval(
        entity_type="proposal", entity_id=proposal.id, action="commit_price"
    )

    async with _lifespan(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            response = await http_client.post(
                f"/approvals/{approval.id}/decide",
                json={"decided_by": "umer@example.com", "decision": "approved"},
                headers=_auth(other_client),
            )

    assert response.status_code == 401
