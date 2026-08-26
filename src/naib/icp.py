"""ICP rubric loading. `Client.icp_config` is per-client jsonb
(docs/ARCHITECTURE.md § Data model), set during onboarding (Phase 8). Until a
client has one configured, `DEFAULT_ICP_CONFIG` is a genuinely reasonable
starting rubric for a small services agency — unlike the Phase 1 playbook,
this is not fake data standing in for something only Umer can supply; it is
a sensible default meant to be tuned per client, the same way `settings.py`
ships real threshold defaults.
"""

from typing import Any

from naib.schemas.icp_config import ICPConfig, ICPCriterion

DEFAULT_ICP_CONFIG = ICPConfig(
    criteria=[
        ICPCriterion(
            name="clear_service_request",
            description="The message names a specific service we offer, not a vague ask",
            weight=0.3,
        ),
        ICPCriterion(
            name="budget_signal_present",
            description="A budget, timeline, or willingness-to-pay signal is present",
            weight=0.3,
        ),
        ICPCriterion(
            name="decision_maker_language",
            description="Sender writes as the decision-maker or a close proxy, not a "
            "student project",
            weight=0.2,
        ),
        ICPCriterion(
            name="market_fit",
            description="Business is a small/mid services business, not an agency "
            "shopping for a subcontractor",
            weight=0.2,
        ),
    ],
    qualify_threshold=0.6,
    hard_disqualifiers=["existing_client", "legal_or_compliance_language", "competitor_scouting"],
)


def load_icp_config(client_icp_config: dict[str, Any] | None) -> ICPConfig:
    """Validate a client's stored `icp_config` jsonb, falling back to the
    default rubric when the client hasn't configured one yet."""

    if not client_icp_config:
        return DEFAULT_ICP_CONFIG
    return ICPConfig.model_validate(client_icp_config)


def render_icp_rubric(config: ICPConfig) -> str:
    """Render the rubric as instruction text for `QualifierAgent`."""

    lines = ["ICP rubric — score against each criterion, then combine into an overall score:"]
    for criterion in config.criteria:
        lines.append(f"- {criterion.name} (weight {criterion.weight}): {criterion.description}")
    lines.append(f"\nQualify threshold: {config.qualify_threshold}")
    lines.append(
        "Hard disqualifiers (any one present -> qualified=False regardless of score): "
        + ", ".join(config.hard_disqualifiers)
    )
    return "\n".join(lines)
