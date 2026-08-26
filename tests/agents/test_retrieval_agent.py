import json
import uuid

from agents import Runner
from agents.testing import ScriptedModel, assistant_message, function_call

from naib.agents.context import NaibContext
from naib.agents.retrieval import build_retrieval_agent
from naib.retrieval import seed_proposal_chunks
from naib.schemas.retrieval_result import RetrievalResult
from naib.store.models import Client
from naib.tools.privileged import PRIVILEGED_TOOL_NAMES


class _FakeEmbedder:
    async def embed(self, text: str) -> list[float]:
        return [0.0] * 1536


def test_retrieval_agent_has_zero_privileged_tools_reachable() -> None:
    agent = build_retrieval_agent(_FakeEmbedder())
    tool_names = {tool.name for tool in agent.tools}

    assert tool_names == {"search_past_proposals"}
    assert tool_names.isdisjoint(PRIVILEGED_TOOL_NAMES)


def test_retrieval_agent_output_type_is_retrieval_result() -> None:
    agent = build_retrieval_agent(_FakeEmbedder())
    assert agent.output_type is RetrievalResult


async def test_retrieval_agent_produces_a_valid_result_via_scripted_tool_call() -> None:
    await seed_proposal_chunks(
        _FakeEmbedder(), [("Bakery Proposal", "Scope: Ordering", "Built an ordering page", True)]
    )

    agent = build_retrieval_agent(_FakeEmbedder())
    agent.model = ScriptedModel(
        [
            [function_call("search_past_proposals", {"query": "ordering site"}, call_id="c1")],
            [
                assistant_message(
                    json.dumps(
                        {
                            "relevant_excerpts": ["Built an ordering page"],
                            "summary": "Found one past proposal covering online ordering.",
                            "confidence": 0.6,
                            "reasons": ["Closest match was an ordering-site scope section"],
                        }
                    )
                )
            ],
        ]
    )

    context = NaibContext(
        client=Client(name="Agency", plan="pilot", playbook_version="v0"),
        lead_id=uuid.uuid4(),
        language="en",
    )
    result = await Runner.run(agent, "Similar past work for: ordering site", context=context)

    assert isinstance(result.final_output, RetrievalResult)
    assert "Built an ordering page" in result.final_output.relevant_excerpts
