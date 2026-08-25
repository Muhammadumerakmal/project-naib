import pytest
from pydantic import BaseModel, ValidationError

from naib.schemas.enrichment_result import EnrichmentResult
from naib.schemas.escalation_brief import EscalationBrief
from naib.schemas.normalized_lead import NormalizedLead
from naib.schemas.proposal_draft import ProposalDraft
from naib.schemas.qualification_result import QualificationResult

AGENT_OUTPUT_SCHEMAS: list[type[BaseModel]] = [
    NormalizedLead,
    QualificationResult,
    EnrichmentResult,
    ProposalDraft,
    EscalationBrief,
]


@pytest.mark.parametrize("schema", AGENT_OUTPUT_SCHEMAS)
def test_every_agent_output_schema_carries_confidence_and_reasons(
    schema: type[BaseModel],
) -> None:
    """CLAUDE.md rule 6: 'Every classification carries a confidence and a
    reason.' A schema missing either field breaks this test on purpose."""

    fields = schema.model_fields
    assert "confidence" in fields
    assert fields["confidence"].annotation is float
    assert "reasons" in fields


def test_normalized_lead_round_trip() -> None:
    lead = NormalizedLead(
        channel="email",
        contact_email="lead@example.com",
        message_summary="Wants a 5-page website.",
        language="en",
        raw_hash="abc123",
        confidence=0.9,
        reasons=["Clear service request", "Valid contact details"],
    )

    assert lead.model_dump()["channel"] == "email"


def test_escalation_brief_requires_all_fields() -> None:
    with pytest.raises(ValidationError):
        EscalationBrief(reason="legal language")  # type: ignore[call-arg]
