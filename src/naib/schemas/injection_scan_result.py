from pydantic import BaseModel


class InjectionScanResult(BaseModel):
    flagged: bool
    matched_patterns: list[str]
    reason: str
