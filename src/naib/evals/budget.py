"""Cost/latency budget runner (docs/EVALS.md: 'Cost per lead <= budget',
'p95 end-to-end latency <= 180s'). Real model calls, real cost — `-m
budget` only, nightly per docs/EVALS.md, never run by default `pytest` or
CI's unit step.
"""

import uuid
from dataclasses import dataclass

from agents import Runner
from sqlmodel import select

from naib.agents.context import NaibContext
from naib.agents.enrichment import build_enrichment_agent
from naib.agents.intake import build_intake_agent
from naib.agents.qualifier import build_qualifier_agent
from naib.agents.retrieval import build_retrieval_agent
from naib.embeddings import OpenAIEmbedder
from naib.events import record_run, record_usage
from naib.guardrails.injection import wrap_untrusted
from naib.icp import load_icp_config
from naib.schemas.golden_record import GoldenRecord
from naib.settings import get_settings
from naib.store.db import get_sessionmaker
from naib.store.models import AgentEvent, Client


@dataclass
class BudgetReport:
    per_lead_costs_usd: list[float]
    latencies_ms: list[int]

    @property
    def max_cost_usd(self) -> float:
        return max(self.per_lead_costs_usd, default=0.0)

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        index = min(int(len(ordered) * 0.95), len(ordered) - 1)
        return ordered[index]


async def run_budget_check(records: tuple[GoldenRecord, ...], client: Client) -> BudgetReport:
    enrichment_agent = build_enrichment_agent()
    retrieval_agent = build_retrieval_agent(OpenAIEmbedder())
    qualifier_agent = build_qualifier_agent(
        load_icp_config(client.icp_config), enrichment_agent, retrieval_agent
    )
    intake_agent = build_intake_agent(qualifier_agent)

    costs: list[float] = []
    latencies: list[int] = []

    for gold in records:
        lead_id = uuid.uuid4()
        context = NaibContext(client=client, lead_id=lead_id, language=gold.language)
        wrapped = wrap_untrusted(gold.raw_message, source=gold.channel)

        async with record_run(agent="IntakeAgent", lead_id=lead_id) as record:
            result = await Runner.run(intake_agent, wrapped, context=context)
            model = intake_agent.model if isinstance(intake_agent.model, str) else None
            record_usage(record, model=model, usage=result.context_wrapper.usage)

        async with get_sessionmaker()() as session:
            events = (
                await session.exec(select(AgentEvent).where(AgentEvent.lead_id == lead_id))
            ).all()

        lead_cost = sum(e.cost_usd or 0.0 for e in events)
        lead_latency = sum(e.latency_ms or 0 for e in events)
        costs.append(lead_cost)
        latencies.append(lead_latency)

    return BudgetReport(per_lead_costs_usd=costs, latencies_ms=latencies)


def budget_ceiling_usd() -> float:
    return get_settings().cost_budget_usd_per_lead
