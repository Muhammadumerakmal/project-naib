"""Rubric graders — judgement-required checks docs/EVALS.md reserves for a
model call, never the deterministic layer (price compliance, schema
validity, permission-tier assertions all live in guardrails/tests instead).
Each grader is a fresh Agent with its own independent instructions and the
strong tier, never reusing the prompt that generated the artifact being
graded (docs/EVALS.md: 'Never grade with the same prompt that generated').
Real model calls — used from the `-m eval`/`-m redteam` suites, never from
default `pytest`.
"""

from agents import Agent, Runner

from naib.schemas.rubric_score import RubricScore
from naib.settings import get_settings

_PROPOSAL_QUALITY_INSTRUCTIONS = """You are an independent quality reviewer, not the agent
that wrote this proposal draft. Score ONE dimension: does the draft read as a competent,
specific, client-ready proposal (not generic filler, grounded in the stated scope)?

Score 1 (generic/unusable) to 5 (excellent, specific, client-ready). Always give a one-
sentence justification citing something concrete from the draft."""

_ESCALATION_USEFULNESS_INSTRUCTIONS = """You are an independent reviewer, not the agent that
wrote this escalation brief. Score ONE dimension: could a human act on this brief within 30
seconds, without needing to go read the original message themselves?

Score 1 (useless, vague, human still has to dig) to 5 (immediately actionable). Always give a
one-sentence justification citing something concrete from the brief."""

_TONE_MATCH_INSTRUCTIONS = """You are an independent reviewer, not the agent that wrote this
text. Score ONE dimension: does the tone match a professional-but-warm small-agency voice —
not stiff corporate boilerplate, not overly casual, no over-styled AI prose (em-dash salad,
listicle-speak)?

Score 1 (wrong tone) to 5 (exactly right). Always give a one-sentence justification citing
something concrete from the text."""


def _build_grader(instructions: str) -> Agent[None]:
    settings = get_settings()
    return Agent[None](
        name="RubricGrader",
        instructions=instructions,
        model=settings.model_strong,
        tools=[],
        output_type=RubricScore,
    )


async def _grade(instructions: str, dimension: str, artifact_text: str) -> RubricScore:
    grader = _build_grader(instructions)
    result = await Runner.run(grader, f"Dimension: {dimension}\n\nText to grade:\n{artifact_text}")
    score = result.final_output
    if not isinstance(score, RubricScore):
        raise TypeError(f"RubricGrader ended without a RubricScore (got {type(score).__name__}).")
    return score


async def grade_proposal_quality(draft_md: str) -> RubricScore:
    return await _grade(_PROPOSAL_QUALITY_INSTRUCTIONS, "proposal_quality", draft_md)


async def grade_escalation_usefulness(brief_md: str) -> RubricScore:
    return await _grade(_ESCALATION_USEFULNESS_INSTRUCTIONS, "escalation_usefulness", brief_md)


async def grade_tone_match(text: str) -> RubricScore:
    return await _grade(_TONE_MATCH_INSTRUCTIONS, "tone_match", text)
