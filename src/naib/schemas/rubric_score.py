from pydantic import BaseModel, Field


class RubricScore(BaseModel):
    """One dimension of a rubric grade. docs/EVALS.md: '1-5 with a required
    justification string', graded independently of the prompt that
    generated the artifact being scored."""

    dimension: str
    score: int = Field(ge=1, le=5)
    justification: str
