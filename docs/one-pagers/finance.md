# Naib — for Finance

*One page, addressed to the person who never took the sales call but signs off on the bill.
Fill in the `{{ }}` placeholders per prospect and hand this to your champion to forward —
that forwarding is the actual sales motion (docs/DEPLOYABILITY.md § 2).*

## What you're worried about

A recurring bill that scales unpredictably with usage you don't control.

## The answer

**Fixed monthly platform fee: {{CURRENCY}} {{MONTHLY_PLATFORM_FEE}}/month**, covering up to
{{INCLUDED_LEAD_VOLUME}} leads. Above that, a **metered per-lead cost** — and that cost is not
a guess, it's measured: every run logs its own token spend (`agent_events.cost_usd`), so the
number in your invoice is the number the eval suite already reported before you were billed
for it.

Current measured cost per lead: **{{CURRENCY}} {{COST_PER_LEAD}}** *(from the budget eval suite
— docs/EVALS.md — not a vendor estimate)*.

## The ceiling, and what enforces it

- A per-lead cost budget (`NAIB_COST_BUDGET_USD_PER_LEAD`) that the enrichment step is hard-capped
  against (`naib.tools.enrichment_tools` — at most {{MAX_ENRICHMENT_CALLS}} lookups per lead).
- Model routing keeps the cheap-and-fast model on every inbound message (including spam) and
  reserves the expensive model for the two outputs a human actually reads: the proposal draft
  and the escalation brief.
- The kill switch stops all spend for your account, instantly, from a screen anyone on your
  team can reach — not a support ticket.

## The pilot is risk transfer, not a discount

30-day paid pilot, on your real inbound, fully approval-gated (nothing sends without a human),
kill switch from day one, all your data exportable, no lock-in. You are not committing to a
platform — you're buying 30 days of evidence.

## One number

> {{ONE_HEADLINE_NUMBER — e.g. "Estimated monthly leakage from unanswered enquiries:
> PKR X. Naib costs PKR Y."}}

*(Generate this line with `naib.sales.risk_calculator` during discovery — see the Defensibility
Pack for the full worksheet.)*
