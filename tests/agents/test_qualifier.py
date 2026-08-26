import json

from agents import Runner
from agents.testing import ScriptedModel, assistant_message

from naib.agents.qualifier import build_qualifier_agent
from naib.icp import DEFAULT_ICP_CONFIG
from naib.schemas.qualification_result import QualificationResult


def test_qualifier_agent_has_no_tools_in_phase_two() -> None:
    """Enrichment/retrieval as agent-as-tool arrive in Phase 3 — see
    docs/ARCHITECTURE.md agent topology."""

    qualifier_agent = build_qualifier_agent(DEFAULT_ICP_CONFIG)
    assert qualifier_agent.tools == []


def test_qualifier_instructions_render_the_configured_rubric() -> None:
    qualifier_agent = build_qualifier_agent(DEFAULT_ICP_CONFIG)
    assert isinstance(qualifier_agent.instructions, str)
    for criterion in DEFAULT_ICP_CONFIG.criteria:
        assert criterion.name in qualifier_agent.instructions


async def test_qualifier_produces_a_valid_qualification_result() -> None:
    qualifier_agent = build_qualifier_agent(DEFAULT_ICP_CONFIG)
    qualifier_agent.model = ScriptedModel(
        [
            [
                assistant_message(
                    json.dumps(
                        {
                            "qualified": False,
                            "score": 0.2,
                            "band": "low",
                            "disqualifiers": ["existing_client"],
                            "should_escalate": True,
                            "confidence": 0.9,
                            "reasons": ["Sender is an existing client thread"],
                        }
                    )
                )
            ]
        ]
    )

    result = await Runner.run(qualifier_agent, "Normalized lead from IntakeAgent:\n{}")

    assert isinstance(result.final_output, QualificationResult)
    assert result.final_output.qualified is False
    assert result.final_output.should_escalate is True
