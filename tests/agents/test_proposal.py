import json
import uuid

import pytest
from agents import OutputGuardrailTripwireTriggered, Runner
from agents.testing import ScriptedModel, assistant_message

from naib.agents.context import NaibContext
from naib.agents.proposal import build_proposal_agent
from naib.playbook import get_playbook_entry, render_price_band
from naib.schemas.proposal_draft import ProposalDraft
from naib.store.models import Client
from naib.tools.privileged import PRIVILEGED_TOOL_NAMES

_ENTRY = get_playbook_entry("placeholder-website-basic")
_GOOD_DRAFT_MD = (
    "Hi Ali,\n\nThanks for reaching out. We'd build a 5-page marketing site for your "
    f"business.\n\nInvestment: {render_price_band(_ENTRY)}.\n\nBest regards,\nNaib"
)


def _context() -> NaibContext:
    return NaibContext(
        client=Client(name="Agency", plan="pilot", playbook_version="v0"),
        lead_id=uuid.uuid4(),
        language="en",
    )


def test_proposal_agent_has_zero_privileged_tools_reachable() -> None:
    agent = build_proposal_agent()
    tool_names = {tool.name for tool in agent.tools}

    assert tool_names == {"list_playbook_entries", "lookup_playbook_entry"}
    assert tool_names.isdisjoint(PRIVILEGED_TOOL_NAMES)
    assert all(not getattr(tool, "needs_approval", False) for tool in agent.tools)


def test_proposal_agent_registers_all_four_output_guardrails() -> None:
    agent = build_proposal_agent()
    guardrail_names = {g.get_name() for g in agent.output_guardrails}
    assert guardrail_names == {
        "price_floor",
        "capability_claim",
        "no_commitment",
        "tone_and_length",
    }


def test_proposal_agent_output_type_is_proposal_draft() -> None:
    agent = build_proposal_agent()
    assert agent.output_type is ProposalDraft


async def test_proposal_agent_produces_a_valid_draft() -> None:
    agent = build_proposal_agent()
    agent.model = ScriptedModel(
        [
            [
                assistant_message(
                    json.dumps(
                        {
                            "playbook_entry_id": _ENTRY.id,
                            "price_band": render_price_band(_ENTRY),
                            "scope_summary": "5-page marketing site",
                            "draft_md": _GOOD_DRAFT_MD,
                            "confidence": 0.85,
                            "reasons": ["Clear match to basic website package"],
                        }
                    )
                )
            ]
        ]
    )

    result = await Runner.run(agent, "Lead wants a basic marketing website.", context=_context())

    assert isinstance(result.final_output, ProposalDraft)
    assert result.final_output.playbook_entry_id == _ENTRY.id


async def test_proposal_agent_tripwire_fires_on_an_invented_price() -> None:
    """Proves the price_floor output guardrail actually halts the run — not
    just that the check function itself returns a reason (already covered
    in tests/guardrails/test_proposal_guardrails.py)."""

    agent = build_proposal_agent()
    agent.model = ScriptedModel(
        [
            [
                assistant_message(
                    json.dumps(
                        {
                            "playbook_entry_id": _ENTRY.id,
                            "price_band": "PKR 12,345 - PKR 54,321",
                            "scope_summary": "5-page marketing site",
                            "draft_md": _GOOD_DRAFT_MD,
                            "confidence": 0.85,
                            "reasons": ["Clear match to basic website package"],
                        }
                    )
                )
            ]
        ]
    )

    with pytest.raises(OutputGuardrailTripwireTriggered) as exc_info:
        await Runner.run(agent, "Lead wants a basic marketing website.", context=_context())

    assert exc_info.value.guardrail_result.guardrail.get_name() == "price_floor"
