from pydantic import BaseModel


class ICPCriterion(BaseModel):
    """One line item in a client's qualification rubric. Weight is relative,
    not a probability — `QualifierAgent` uses these as scoring guidance, it
    does not compute the score by formula (that would just move CLAUDE.md
    rule 4's problem from prices to scores)."""

    name: str
    description: str
    weight: float


class ICPConfig(BaseModel):
    """A client's ideal-customer-profile rubric. Stored as `Client.icp_config`
    jsonb (docs/ARCHITECTURE.md § Data model); loaded and validated against
    this schema before it reaches `QualifierAgent`."""

    criteria: list[ICPCriterion]
    qualify_threshold: float
    hard_disqualifiers: list[str]
