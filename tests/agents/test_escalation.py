import json
import uuid

from agents import Runner
from agents.testing import ScriptedModel, assistant_message

from naib.agents.context import NaibContext
from naib.agents.escalation import build_escalation_agent
from naib.schemas.escalation_brief import EscalationBrief
from naib.store.models import Client
from naib.tools.privileged import PRIVILEGED_TOOL_NAMES


def test_escalation_agent_has_zero_privileged_tools_reachable() -> None:
    agent = build_escalation_agent()
    assert agent.tools == []
    assert set().isdisjoint(PRIVILEGED_TOOL_NAMES)


def test_escalation_agent_output_type_is_escalation_brief() -> None:
    agent = build_escalation_agent()
    assert agent.output_type is EscalationBrief


async def test_escalation_agent_produces_a_valid_brief() -> None:
    agent = build_escalation_agent()
    agent.model = ScriptedModel(
        [
            [
                assistant_message(
                    json.dumps(
                        {
                            "reason": "existing_client",
                            "summary": "Sender asked us to fix a bug on a site we already built.",
                            "conclusion": "Disqualified: existing-client thread.",
                            "why_stopped": "Hard disqualifier 'existing_client' fired.",
                            "recommendation": "Route to account management, not sales.",
                            "confidence": 0.9,
                            "reasons": ["Existing-client hard disqualifier"],
                        }
                    )
                )
            ]
        ]
    )

    context = NaibContext(
        client=Client(name="Agency", plan="pilot", playbook_version="v0"),
        lead_id=uuid.uuid4(),
        language="en",
    )
    result = await Runner.run(agent, "Escalation reason: existing_client", context=context)

    assert isinstance(result.final_output, EscalationBrief)
    assert result.final_output.reason == "existing_client"
