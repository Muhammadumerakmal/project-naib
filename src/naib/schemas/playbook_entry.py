from typing import Self

from pydantic import BaseModel, model_validator


class PlaybookEntry(BaseModel):
    """One row of the services catalogue. The ProposalAgent selects a band
    from here — it may not compute or invent one. See CLAUDE.md rule 4.

    `is_placeholder` lets downstream code (and tests) refuse to build a real
    proposal or commit a real price off fake data — see naib.playbook.
    """

    id: str
    service_name: str
    description: str
    scope_template: str
    capabilities: list[str]
    price_band_low: int
    price_band_high: int
    currency: str = "PKR"
    is_placeholder: bool = False

    @model_validator(mode="after")
    def _price_band_is_ordered(self) -> Self:
        if self.price_band_low > self.price_band_high:
            raise ValueError("price_band_low must be <= price_band_high")
        return self
