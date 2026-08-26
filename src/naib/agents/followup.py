"""FollowUpAgent — cadence composer for an approved proposal that hasn't
had a reply yet. Fast tier: only proposal drafts and escalation briefs are
strong-tier (docs/ARCHITECTURE.md § Model routing) — a follow-up nudge is
lower-stakes composition. No tools that write anything; drafts only, same
as every other agent here.
"""

from agents import Agent

from naib.agents.context import NaibContext
from naib.schemas.followup_draft import FollowUpDraft
from naib.settings import get_settings

_INSTRUCTIONS = """You are FollowUpAgent for Naib. A proposal was approved and sent, but the
client hasn't replied. Write one short, low-pressure follow-up message.

You receive the original proposal's scope summary and price band, the attempt number, and how
many days have passed since the proposal was approved. Keep it brief — a follow-up is a nudge,
not a re-pitch. Reference the original proposal naturally; do not repeat the full scope or
price again unless attempt_number is 1. Never add a new commitment, deadline, or discount that
wasn't in the original proposal — you are not authorised to change the offer.

This is a draft only. It is never sent without a human approving it first.
"""


def build_followup_agent() -> Agent[NaibContext]:
    settings = get_settings()
    return Agent[NaibContext](
        name="FollowUpAgent",
        instructions=_INSTRUCTIONS,
        model=settings.model_fast,
        tools=[],
        output_type=FollowUpDraft,
    )
