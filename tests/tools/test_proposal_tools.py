import uuid

from agents.tool_context import ToolContext

from naib.agents.context import NaibContext
from naib.playbook import get_playbook_entry, render_price_band
from naib.store.models import Client
from naib.tools.proposal_tools import list_playbook_entries, lookup_playbook_entry


def _fake_tool_ctx(*, tool_name: str) -> ToolContext[NaibContext]:
    context = NaibContext(
        client=Client(name="x", plan="pilot", playbook_version="v0"),
        lead_id=uuid.uuid4(),
        language="en",
    )
    return ToolContext(
        context=context, tool_name=tool_name, tool_call_id="call-1", tool_arguments="{}"
    )


async def test_list_playbook_entries_returns_every_entry() -> None:
    result = await list_playbook_entries.on_invoke_tool(
        _fake_tool_ctx(tool_name="list_playbook_entries"), "{}"
    )
    ids = {entry.id for entry in result}
    assert "placeholder-website-basic" in ids
    assert "placeholder-ecommerce-standard" in ids


async def test_lookup_playbook_entry_returns_the_canonical_price_band() -> None:
    entry = get_playbook_entry("placeholder-website-basic")
    result = await lookup_playbook_entry.on_invoke_tool(
        _fake_tool_ctx(tool_name="lookup_playbook_entry"),
        '{"entry_id": "placeholder-website-basic"}',
    )
    assert result.price_band == render_price_band(entry)
    assert result.capabilities == entry.capabilities
