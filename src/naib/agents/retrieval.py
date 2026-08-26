"""RetrievalAgent — agent-as-tool over past *won* proposals, chunked by
scope section and searched via pgvector cosine distance
(`naib.retrieval.search_past_proposals`). Same agent-as-tool reasoning as
EnrichmentAgent: it returns a value QualifierAgent still needs to finish
scoring. See docs/ARCHITECTURE.md and PLAN.md Phase 3.
"""

from agents import Agent, function_tool

from naib.agents.context import NaibContext
from naib.embeddings import Embedder
from naib.retrieval import search_past_proposals
from naib.schemas.retrieval_result import RetrievalResult
from naib.settings import get_settings

_INSTRUCTIONS = """You are RetrievalAgent for Naib. QualifierAgent calls you as a tool to check
whether past won proposals cover similar work, which is useful context for scoring fit.

Call search_past_proposals with a short query describing the requested service. Summarize what
the retrieved excerpts show; a low match (or none at all) is a valid, honest answer — do not
invent similarity that isn't there. Some seeded proposals are synthetic placeholders pending
real client data; treat them the same as any other result, you have no way to tell the
difference and shouldn't need to.
"""


def build_retrieval_agent(embedder: Embedder) -> Agent[NaibContext]:
    settings = get_settings()

    @function_tool(name_override="search_past_proposals")
    async def search_past_proposals_tool(query: str) -> list[dict[str, str | float]]:
        """Search past won proposals for excerpts relevant to `query`."""

        chunks = await search_past_proposals(query, embedder, limit=3)
        return [
            {
                "proposal_label": c.proposal_label,
                "scope_section": c.scope_section,
                "chunk_text": c.chunk_text,
                "distance": c.distance,
            }
            for c in chunks
        ]

    return Agent[NaibContext](
        name="RetrievalAgent",
        instructions=_INSTRUCTIONS,
        model=settings.model_fast,
        tools=[search_past_proposals_tool],
        output_type=RetrievalResult,
    )
