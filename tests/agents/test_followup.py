import json
import uuid

from agents import Runner
from agents.testing import ScriptedModel, assistant_message

from naib.agents.context import NaibContext
from naib.agents.followup import build_followup_agent
from naib.schemas.followup_draft import FollowUpDraft
from naib.settings import get_settings
from naib.store.models import Client
from naib.tools.privileged import PRIVILEGED_TOOL_NAMES


def test_followup_agent_has_zero_privileged_tools_reachable() -> None:
    agent = build_followup_agent()
    assert agent.tools == []
    assert set().isdisjoint(PRIVILEGED_TOOL_NAMES)


def test_followup_agent_output_type_is_followup_draft() -> None:
    agent = build_followup_agent()
    assert agent.output_type is FollowUpDraft


def test_followup_agent_uses_the_fast_tier() -> None:
    """Only proposal drafts and escalation briefs are strong-tier — see
    docs/ARCHITECTURE.md § Model routing."""

    agent = build_followup_agent()
    assert agent.model == get_settings().model_fast


async def test_followup_agent_produces_a_valid_draft() -> None:
    agent = build_followup_agent()
    agent.model = ScriptedModel(
        [
            [
                assistant_message(
                    json.dumps(
                        {
                            "message_md": "Hi Ali, just checking in on the proposal I sent last "
                            "week — happy to answer any questions. Best, Naib",
                            "confidence": 0.7,
                            "reasons": ["First follow-up, keeping it brief"],
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
    result = await Runner.run(agent, "Attempt number 1 of 3.", context=context)

    assert isinstance(result.final_output, FollowUpDraft)
