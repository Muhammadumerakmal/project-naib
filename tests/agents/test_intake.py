"""Structural + wiring tests for IntakeAgent. No real model calls — the SDK's
own `ScriptedModel` test double proves the plumbing deterministically, at
zero cost (docs/EVALS.md unit tier). The one thing worth a real eval-suite
run against a real model is qualification *accuracy*, which is what
tests/evals/test_golden_set.py is for.
"""

import json
import uuid

from agents import Agent, Runner
from agents.testing import ScriptedModel, assistant_message, function_call

from naib.agents.context import NaibContext
from naib.agents.intake import build_intake_agent
from naib.agents.qualifier import build_qualifier_agent
from naib.guardrails.injection import wrap_untrusted
from naib.icp import DEFAULT_ICP_CONFIG
from naib.store.models import Client
from naib.tools.privileged import PRIVILEGED_TOOL_NAMES


def _build_pair() -> tuple[Agent[NaibContext], Agent[NaibContext]]:
    qualifier_agent = build_qualifier_agent(DEFAULT_ICP_CONFIG)
    intake_agent = build_intake_agent(qualifier_agent)
    return intake_agent, qualifier_agent


def test_intake_agent_has_zero_privileged_tools_reachable() -> None:
    """CLAUDE.md rule 1 + docs/ARCHITECTURE.md Phase 2 gate: assert this in
    a test, not by reading the code."""

    intake_agent, _qualifier_agent = _build_pair()

    tool_names = {tool.name for tool in intake_agent.tools}
    assert tool_names.isdisjoint(PRIVILEGED_TOOL_NAMES)
    assert all(not getattr(tool, "needs_approval", False) for tool in intake_agent.tools)


def test_intake_agent_registers_all_four_input_guardrails() -> None:
    intake_agent, _qualifier_agent = _build_pair()

    guardrail_names = {g.get_name() for g in intake_agent.input_guardrails}
    assert guardrail_names == {
        "injection_scan",
        "is_actual_lead",
        "pii_minimize",
        "language_route",
    }


def test_intake_agent_has_no_output_type_only_a_handoff() -> None:
    """IntakeAgent's job ends with the handoff, not a final message — see
    module docstring in naib.agents.intake."""

    intake_agent, qualifier_agent = _build_pair()

    assert intake_agent.output_type is None
    assert len(intake_agent.handoffs) == 1
    assert intake_agent.handoffs[0].agent_name == qualifier_agent.name


async def test_handoff_carries_only_the_normalized_lead_not_raw_text() -> None:
    """The security property from docs/ARCHITECTURE.md: 'Downstream agents
    never see the raw text.' Proven by inspecting exactly what QualifierAgent's
    model call received."""

    intake_agent, qualifier_agent = _build_pair()
    handoff_tool_name = intake_agent.handoffs[0].tool_name

    normalized_lead_args = {
        "channel": "email",
        "contact_name": "Ali",
        "contact_email": "ali@example.com",
        "contact_phone": None,
        "company_name": "Ali Clinic",
        "message_summary": "Wants a 5-page website.",
        "requested_service": "website",
        "budget_signal": "PKR 80,000",
        "language": "en",
        "raw_hash": "deadbeef",
        "confidence": 0.9,
        "reasons": ["Clear service request", "Budget stated"],
    }

    intake_model = ScriptedModel(
        [[function_call(handoff_tool_name, normalized_lead_args, call_id="call-handoff-1")]]
    )
    qualifier_model = ScriptedModel(
        [
            [
                assistant_message(
                    json.dumps(
                        {
                            "qualified": True,
                            "score": 0.8,
                            "band": "high",
                            "disqualifiers": [],
                            "should_escalate": False,
                            "confidence": 0.85,
                            "reasons": ["Clear service request", "Budget stated"],
                        }
                    )
                )
            ]
        ]
    )
    intake_agent.model = intake_model
    qualifier_agent.model = qualifier_model

    # Ordinary lead text — deliberately free of injection-pattern words, since
    # this test proves the raw-text-stripping property, not the injection
    # guardrail (that's covered separately in tests/guardrails/test_injection.py).
    # It carries a marker phrase that must never reach QualifierAgent.
    marker_phrase = "please keep my cell number private from anyone else at your agency"
    raw_untrusted_text = wrap_untrusted(
        f"Hi, I need a website for my clinic. {marker_phrase}. — Ali",
        source="email",
    )

    context = NaibContext(
        client=Client(name="Agency", plan="pilot", playbook_version="v0"),
        lead_id=uuid.uuid4(),
        language="en",
    )

    result = await Runner.run(intake_agent, raw_untrusted_text, context=context)

    assert context.normalized_lead is not None
    assert context.normalized_lead.contact_email == "ali@example.com"

    qualifier_call = qualifier_model.last_call
    assert qualifier_call is not None
    call_input_text = (
        qualifier_call.input
        if isinstance(qualifier_call.input, str)
        else json.dumps(qualifier_call.input)
    )
    assert marker_phrase not in call_input_text
    assert "===UNTRUSTED-CONTENT===" not in call_input_text
    assert "ali@example.com" in call_input_text

    assert result.last_agent.name == "QualifierAgent"
