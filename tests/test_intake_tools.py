import uuid

from agents.tool_context import ToolContext

from naib.agents.context import NaibContext
from naib.store.db import get_sessionmaker
from naib.store.models import Client, Lead
from naib.tools.intake_tools import extract_contact_info, lookup_existing_lead


def _fake_tool_ctx(*, tool_name: str) -> ToolContext[NaibContext]:
    context = NaibContext(
        client=Client(name="x", plan="pilot", playbook_version="v0"),
        lead_id=uuid.uuid4(),
        language="en",
    )
    return ToolContext(
        context=context,
        tool_name=tool_name,
        tool_call_id="call-1",
        tool_arguments="{}",
    )


async def test_extract_contact_info_finds_email_and_phone() -> None:
    result = await extract_contact_info.on_invoke_tool(
        _fake_tool_ctx(tool_name="extract_contact_info"),
        '{"text": "Reach me at ali@example.com or 03001234567."}',
    )
    assert "ali@example.com" in result.emails
    assert "03001234567" in result.phones


async def test_extract_contact_info_dedupes() -> None:
    result = await extract_contact_info.on_invoke_tool(
        _fake_tool_ctx(tool_name="extract_contact_info"),
        '{"text": "ali@example.com, again ali@example.com"}',
    )
    assert result.emails == ["ali@example.com"]


async def test_lookup_existing_lead_true_after_prior_lead() -> None:
    async with get_sessionmaker()() as session:
        client = Client(name="Agency", plan="pilot", playbook_version="v0")
        session.add(client)
        await session.commit()
        await session.refresh(client)

        lead = Lead(
            client_id=client.id,
            channel="email",
            raw_hash="abc",
            normalized={"contact_email": "returning@example.com"},
        )
        session.add(lead)
        await session.commit()

    found = await lookup_existing_lead.on_invoke_tool(
        _fake_tool_ctx(tool_name="lookup_existing_lead"),
        f'{{"client_id": "{client.id}", "contact_email": "returning@example.com"}}',
    )
    not_found = await lookup_existing_lead.on_invoke_tool(
        _fake_tool_ctx(tool_name="lookup_existing_lead"),
        f'{{"client_id": "{client.id}", "contact_email": "nobody@example.com"}}',
    )
    assert found is True
    assert not_found is False
