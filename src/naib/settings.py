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

    # Phase 2.5 voice channel — Twilio Basic Auth credentials for fetching a
    # recording before transcription. Empty until a client's Twilio number is
    # connected at onboarding (Phase 8).
    twilio_account_sid: str = Field(default="", validation_alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(default="", validation_alias="TWILIO_AUTH_TOKEN")

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

    # Phase 5 follow-up cadence — exhaustion rules (PLAN.md: "gated").
    max_followup_attempts: int = Field(default=3, validation_alias="NAIB_MAX_FOLLOWUP_ATTEMPTS")
    followup_interval_days: int = Field(default=3, validation_alias="NAIB_FOLLOWUP_INTERVAL_DAYS")

    # Phase 6 trace export — HMAC key for the signed per-lead JSON bundle a
    # client can inspect. Empty in dev; must be set before Phase 8 deploy.
    trace_export_secret: str = Field(default="", validation_alias="NAIB_TRACE_EXPORT_SECRET")

    # Phase 6 client report — "cost vs. the human hour it displaced" needs a
    # baseline for what manual intake+qualification would have cost. These
    # are placeholder estimates, not measured facts — calibrate against
    # Umer's own numbers during Phase 8 dogfooding.
    human_minutes_per_lead_baseline: float = Field(
        default=15.0, validation_alias="NAIB_HUMAN_MINUTES_PER_LEAD_BASELINE"
    )
    human_hourly_cost_usd: float = Field(
        default=10.0, validation_alias="NAIB_HUMAN_HOURLY_COST_USD"
    )

    # Safety. There is deliberately no flag that disables approval in v1 —
    # every send/write/commit tool is needs_approval=True regardless of this.
    kill_switch: bool = Field(default=False, validation_alias="NAIB_KILL_SWITCH")
    autonomy_level: str = Field(default="draft_only", validation_alias="NAIB_AUTONOMY_LEVEL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
