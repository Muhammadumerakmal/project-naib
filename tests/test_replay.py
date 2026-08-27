import json
from typing import Any

import pytest
from agents.testing import ScriptedModel, assistant_message
from sqlmodel import select

from naib import replay as replay_module
from naib.agents.qualifier import build_qualifier_agent
from naib.icp import DEFAULT_ICP_CONFIG
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead, Qualification

_NORMALIZED_LEAD_DICT: dict[str, Any] = {
    "channel": "email",
    "contact_name": "Ali",
    "contact_email": "ali@example.com",
    "contact_phone": None,
    "company_name": None,
    "message_summary": "Wants a website.",
    "requested_service": "website",
    "budget_signal": None,
    "language": "en",
    "raw_hash": "replay-test",
    "confidence": 0.9,
    "reasons": ["x"],
}


def _wire_scripted_qualifier(monkeypatch: pytest.MonkeyPatch, *, response: dict) -> None:
    def _build_qualifier(
        icp_config: object, enrichment_agent: object, retrieval_agent: object
    ) -> object:
        agent = build_qualifier_agent(
            DEFAULT_ICP_CONFIG, enrichment_agent, retrieval_agent  # type: ignore[arg-type]
        )
        agent.model = ScriptedModel([[assistant_message(json.dumps(response))]])
        return agent

    monkeypatch.setattr(replay_module, "build_qualifier_agent", _build_qualifier)


async def _make_client_and_lead(
    *, normalized: dict[str, Any] | None = _NORMALIZED_LEAD_DICT
) -> tuple[Client, Lead]:
    async with get_sessionmaker()() as session:
        client = Client(name="Replay Test Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(
            client_id=client.id, channel="email", raw_hash="replay-test", normalized=normalized
        )
        session.add(lead)
        await session.commit()
        await session.refresh(lead)
    return client, lead


async def test_replay_lead_raises_for_a_lead_with_no_normalized_data() -> None:
    _client, lead = await _make_client_and_lead(normalized=None)

    with pytest.raises(ValueError, match="nothing to replay"):
        await replay_module.replay_lead(lead.id)


async def test_replay_lead_persists_a_fresh_qualification_and_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _client, lead = await _make_client_and_lead()
    _wire_scripted_qualifier(
        monkeypatch,
        response={
            "qualified": False,
            "score": 0.2,
            "band": "low",
            "disqualifiers": ["existing_client"],
            "should_escalate": True,
            "confidence": 0.9,
            "reasons": ["replayed"],
        },
    )

    routed: dict[str, object] = {}

    async def _fake_route(lead_id: str, client: Client, qualification: object) -> str:
        routed["lead_id"] = lead_id
        routed["qualification"] = qualification
        return "escalated:qualifier_flagged"

    monkeypatch.setattr(replay_module, "_route_qualified_lead", _fake_route)

    result = await replay_module.replay_lead(lead.id)

    assert result.qualification.qualified is False
    assert result.routing_status == "escalated:qualifier_flagged"
    assert routed["lead_id"] == str(lead.id)

    async with get_sessionmaker()() as session:
        qualifications = (
            await session.exec(select(Qualification).where(Qualification.lead_id == lead.id))
        ).all()
    assert len(qualifications) == 1
    assert qualifications[0].band == "low"
