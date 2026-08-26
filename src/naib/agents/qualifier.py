"""QualifierAgent — scores a validated `NormalizedLead` against the client's
ICP rubric and produces a `QualificationResult`. Never sees raw untrusted
text (see the Intake -> Qualifier handoff's `input_filter` in
`naib.agents.pipeline`). As of Phase 3, calls EnrichmentAgent and
RetrievalAgent as agent-as-tools (docs/ARCHITECTURE.md): both return a
value the qualifier still needs to finish scoring, so a handoff would
strand it mid-decision."""

from agents import Agent

from naib.agents.context import NaibContext
from naib.icp import render_icp_rubric
from naib.schemas.icp_config import ICPConfig
from naib.schemas.qualification_result import QualificationResult
from naib.settings import get_settings

_BASE_INSTRUCTIONS = """You are QualifierAgent for Naib, an inbound revenue-ops assistant.

You receive one validated, structured lead (already extracted by IntakeAgent — you never see
the sender's raw message). Score it against the ICP rubric below and produce a
QualificationResult.

You have two optional tools: enrichment (public web lookup on the lead's company) and
retrieval (search past won proposals for similar work). Use them when the lead gives you a
company name or a clear service request worth checking — not on every lead. Both can come back
empty or low-confidence; that is a valid input to your scoring, not a reason to keep retrying.

Rules:
- qualified=True only if the score clears the qualify_threshold AND no hard disqualifier
  applies. A hard disqualifier present means qualified=False regardless of score.
- should_escalate=True whenever confidence is low, a hard disqualifier fired, or signals
  conflict (e.g. strong budget signal but also a hard disqualifier).
- Every score and every disqualifier claim needs a one-line reason in `reasons`.
- You never draft a reply, quote a price, or claim a capability — that is not your job.
"""


def _instructions(icp_config: ICPConfig) -> str:
    return f"{_BASE_INSTRUCTIONS}\n{render_icp_rubric(icp_config)}"


def build_qualifier_agent(
    icp_config: ICPConfig,
    enrichment_agent: Agent[NaibContext],
    retrieval_agent: Agent[NaibContext],
) -> Agent[NaibContext]:
    settings = get_settings()
    return Agent[NaibContext](
        name="QualifierAgent",
        instructions=_instructions(icp_config),
        model=settings.model_fast,
        tools=[
            enrichment_agent.as_tool(
                tool_name="enrich_lead",
                tool_description=(
                    "Look up a lead's company on the public web: site fetch, stack "
                    "detection, size estimate."
                ),
            ),
            retrieval_agent.as_tool(
                tool_name="retrieve_past_proposals",
                tool_description="Search past won proposals for excerpts relevant to a query.",
            ),
        ],
        output_type=QualificationResult,
    )
