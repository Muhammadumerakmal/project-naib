"""Central configuration. Every threshold, model name, and flag lives here —
never hardcoded in an agent, tool, or guardrail. See .env.example for the full
list of env vars this reads."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Model routing — cheap tier for classification (runs on every inbound
    # message including spam), strong tier for the two outputs a human reads.
    model_fast: str = Field(default="gpt-4.1-mini", validation_alias="NAIB_MODEL_FAST")
    model_strong: str = Field(default="gpt-4.1", validation_alias="NAIB_MODEL_STRONG")

    openai_api_key: str = ""
    openai_agents_disable_tracing: bool = False

    database_url: str = "postgresql+asyncpg://naib:naib@localhost:5432/naib"
    redis_url: str = "redis://localhost:6379/0"

    # Thresholds
    qualify_confidence_min: float = Field(
        default=0.75, validation_alias="NAIB_QUALIFY_CONFIDENCE_MIN"
    )
    escalate_below: float = Field(default=0.60, validation_alias="NAIB_ESCALATE_BELOW")
    price_floor_pkr: int = Field(default=0, validation_alias="NAIB_PRICE_FLOOR_PKR")
    cost_budget_usd_per_lead: float = Field(
        default=0.15, validation_alias="NAIB_COST_BUDGET_USD_PER_LEAD"
    )
    max_enrichment_calls: int = Field(default=4, validation_alias="NAIB_MAX_ENRICHMENT_CALLS")

    # Safety. There is deliberately no flag that disables approval in v1 —
    # every send/write/commit tool is needs_approval=True regardless of this.
    kill_switch: bool = Field(default=False, validation_alias="NAIB_KILL_SWITCH")
    autonomy_level: str = Field(default="draft_only", validation_alias="NAIB_AUTONOMY_LEVEL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
