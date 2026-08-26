"""Names reserved for the privileged tier (docs/ARCHITECTURE.md § Tools,
write/approval-gated). No implementation lives here yet — `draft_proposal_doc`
and `write_crm` arrive in Phase 4/5. This module exists so every agent's
tool list can be asserted against it *before* those tools exist, per
CLAUDE.md rule 2: 'needs_approval=True... There is no config flag that turns
this off.'
"""

PRIVILEGED_TOOL_NAMES = frozenset(
    {
        "send_email",
        "send_whatsapp",
        "write_crm",
        "commit_price",
        "draft_proposal_doc",
        "schedule_followup",
    }
)
