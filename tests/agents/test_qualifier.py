import json

from agents import Agent, Runner
from agents.testing import ScriptedModel, assistant_message

from naib.agents.context import NaibContext
from naib.agents.enrichment import build_enrichment_agent
from naib.agents.qualifier import build_qualifier_agent
from naib.agents.retrieval import build_retrieval_agent
from naib.icp import DEFAULT_ICP_CONFIG
from naib.schemas.qualification_result import QualificationResult
from naib.tools.privileged import PRIVILEGED_TOOL_NAMES


class _FakeEmbedder:
    async def embed(self, text: str) -> list[float]:
        return [0.0] * 1536


def _build() -> Agent[NaibContext]:
    return build_qualifier_agent(
        DEFAULT_ICP_CONFIG, build_enrichment_agent(), build_retrieval_agent(_FakeEmbedder())
    )


def test_qualifier_agent_exposes_enrichment_and_retrieval_as_tools_only() -> None:
    """Phase 3: EnrichmentAgent/RetrievalAgent arrive as agent-as-tool — see
    docs/ARCHITECTURE.md agent topology. Still zero privileged tools."""

    qualifier_agent = _build()
    tool_names = {tool.name for tool in qualifier_agent.tools}

    assert tool_names == {"enrich_lead", "retrieve_past_proposals"}
    assert tool_names.isdisjoint(PRIVILEGED_TOOL_NAMES)


def test_qualifier_instructions_render_the_configured_rubric() -> None:
    qualifier_agent = _build()
    assert isinstance(qualifier_agent.instructions, str)
    for criterion in DEFAULT_ICP_CONFIG.criteria:
        assert criterion.name in qualifier_agent.instructions


async def test_qualifier_produces_a_valid_qualification_result() -> None:
    qualifier_agent = _build()
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
