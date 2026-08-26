"""ProposalAgent — strong tier, bound to the playbook. Never sees raw
untrusted text (built from a validated QualificationResult/NormalizedLead,
never a lead's own words directly); has no tools that write anything.
Drafting a proposal and getting a human to approve it are two separate
steps — see `naib.agents.proposal_pipeline` for how a draft becomes an
approval-queue entry, and the Phase 4 handoff for why that step does not
use the SDK's native tool-approval/interruption mechanism.
"""

from agents import Agent

from naib.agents.context import NaibContext
from naib.guardrails.proposal_guardrails import PROPOSAL_OUTPUT_GUARDRAILS
from naib.schemas.proposal_draft import ProposalDraft
from naib.settings import get_settings
from naib.tools.proposal_tools import list_playbook_entries, lookup_playbook_entry

_INSTRUCTIONS = """You are ProposalAgent for Naib. You draft one proposal for a qualified lead.

You receive a validated, structured summary of the lead (company, requested service, scope
signals) and its qualification — never the sender's raw message.

Steps:
1. Call list_playbook_entries and pick the single best-matching service. If nothing matches
   well, say so honestly in `reasons` and pick the closest — never invent a service.
2. Call lookup_playbook_entry for that entry. Use its price_band string VERBATIM as
   ProposalDraft.price_band — never reformat it, never compute a number yourself, never
   average or split a band.
3. Write draft_md as a short client-facing message: a greeting, a one-paragraph scope summary
   grounded only in that entry's scope_template and capabilities, the price band, and a
   sign-off. No delivery dates, no guarantees, no contractual language — those are commitments
   only a human makes.
4. Never claim a capability that isn't in the chosen entry's capabilities list.

You draft. You do not send, approve, or commit anything — that is a human's decision.
"""


def build_proposal_agent() -> Agent[NaibContext]:
    settings = get_settings()
    return Agent[NaibContext](
        name="ProposalAgent",
        instructions=_INSTRUCTIONS,
        model=settings.model_strong,
        tools=[list_playbook_entries, lookup_playbook_entry],
        output_type=ProposalDraft,
        output_guardrails=PROPOSAL_OUTPUT_GUARDRAILS,
    )
