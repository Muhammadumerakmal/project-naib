# PLAN.md — Naib build plan

Nine phases. Run one at a time with `/phase <n>`. Do not start a phase until the previous
phase's **Gate** passes. Items marked **`[YOU]`** are Umer's 10% and cannot be delegated.

---

## Phase 0 — Guardrail scaffolding (before any agent exists)

Most agentic projects build agents first and bolt safety on at the end, which is why most of
them stall in pilot. We invert it: the cage is built before the animal.

**Build**
- `uv` project, `src/naib/` layout, ruff + mypy strict + pytest configured and passing
- `settings.py` (pydantic-settings): model tiers, thresholds, price floor, feature flags
- `store/` — Postgres schema from `docs/ARCHITECTURE.md`, migrations, async session
- `events.py` — the append-only event writer, with a context manager that wraps every run
- `guardrails/injection.py` — first pass scanner + the delimiter-wrapping utility
- Docker Compose: app + postgres + redis
- CI: lint, types, unit tests on every push

**Gate** — `uv run pytest` green, `mypy` clean, event writer proven by a test that runs a
trivial agent and asserts a complete event row lands in Postgres.

---

## Phase 1 — Domain model and the trust ledger

**Build**
- All Pydantic schemas: `NormalizedLead`, `QualificationResult`, `EnrichmentResult`,
  `ProposalDraft`, `EscalationBrief`. Every one carries `confidence: float` and
  `reasons: list[str]`.
- `approvals` table + service: request, queue, decide, capture edit diff
- `PostgresSession` implementing the SDK session interface
- Playbook loader: services catalogue, price bands, scope templates as structured data
- **`[YOU]`** Fill the playbook with your real services, real scope templates, and real
  price bands. Nobody else can write this. The whole system's honesty depends on it.

**Gate** — Round-trip test: a fabricated lead → approval request → human decision → edit
diff persisted. Playbook validates against schema with zero placeholder rows.

---

## Phase 2 — Intake + Qualifier (one pipeline, production standard)

This is the "one agent done properly" milestone. If you had to stop the project here, this
alone would be sellable.

**Build**
- `IntakeAgent`: read-only tools, cheap tier, structured output, untrusted-text protocol
- `QualifierAgent`: ICP rubric scoring, structured output, confidence + reasons
- Handoff Intake → Qualifier, correctly typed
- Input guardrails: `is_actual_lead`, `injection_scan`, `pii_minimize`, `language_route`
- Roman Urdu + Urdu handling — a real requirement in this market and a genuine moat
  against generic US-built competitors
- FastAPI webhook + arq worker, end to end
- **`[YOU]`** Hand over 40–60 real inbound messages from your own agency, labelled
  qualified / not qualified / escalate. This is the golden set. It cannot be synthesised.

**Gate** — Qualification agreement with your labels ≥ 85% on held-out set. Zero privileged
tools reachable from `IntakeAgent` (assert this in a test, not by reading the code).

---

## Phase 3 — Enrichment and retrieval as tools

**Build**
- `EnrichmentAgent` as agent-as-tool: company lookup, site fetch, stack detection
- `fetch_page` with a tool guardrail — fetched pages are untrusted content, same rules
- `RetrievalAgent` as agent-as-tool over past won proposals (pgvector, chunked by scope
  section, not by arbitrary character count)
- Caching + budget cap per lead so enrichment cannot run away with the cost

**Gate** — Cost per lead measured and under budget. Red-team test: a poisoned page injected
into enrichment does not alter qualification output.

---

## Phase 4 — Proposal agent and the approval gate

**Build**
- `ProposalAgent`: strong tier, bound to playbook, may select a band but never compute one
- Output guardrails: `price_floor`, `capability_claim`, `no_commitment`, `tone_and_length`
- `draft_proposal_doc` + `commit_price` both `needs_approval=True`
- Approval queue API + the resumable approval flow through the SDK runner
- **`[YOU]`** Approve or edit the first 20 drafts yourself. Your edits are training signal
  for the prompt and the single best source of house voice.

**Gate** — 20 drafts reviewed. Zero prices outside playbook bands. Zero invented
capabilities. Edit rate recorded as the baseline you will improve against.

---

## Phase 5 — Escalation and follow-up

**Build**
- `EscalationAgent`: writes a brief a human can act on in 30 seconds — what came in, what
  it concluded, exactly why it stopped, what it recommends
- Confidence-threshold routing, plus hard escalation triggers (legal language, existing
  client, budget conflict)
- `FollowUpAgent`: cadence composer, scheduled runs against the same session, gated
- Exhaustion rules and clean hand-back to human

**Gate** — Escalation precision ≥ 80% (escalations a human agrees were correct) and recall
≥ 95% on the "should have escalated" slice. Recall matters more than precision here: a
false escalation costs 30 seconds, a missed one costs a client.

---

## Phase 6 — Eval harness and red team

**Build** — everything in `docs/EVALS.md`: golden-set runner, rubric graders, injection
suite, cost/latency budgets, regression tracking, `/ship-check` wired to real thresholds
- Trace export: a signed JSON bundle per lead a client can inspect

**Gate** — Full suite runs in CI. Thresholds enforced. A deliberately broken prompt must
fail the suite — verify the harness can actually detect regression, or it is theatre.

---

## Phase 7 — Dashboard (the thing you demo)

**Build** — React + Vite + TanStack Query + shadcn/ui
- Approval queue (the daily-driver screen)
- Trace viewer: every step, guardrail outcome, cost, in plain language
- Escalations inbox
- Charts: edit rate over time, cost per lead, injections blocked, time-to-first-response
- Kill switch, visible and unmissable

Design note: this UI's job is *reassurance*, not density. The buyer is a Head of Ops who is
nervous. Every screen should answer "what did it do and can I stop it."

**Gate** — A non-technical person navigates the approval queue and stops a run, unaided.

---

## Phase 8 — Deploy, pilot, and package

**Build**
- Compose deploy on VPS, backups, log retention, per-client isolation
- Onboarding flow: ICP config, playbook import, channel connection
- Kill switch tested in production conditions
- Graduated autonomy: per-client, per-action, unlockable after clean-log thresholds
- Everything in `docs/DEPLOYABILITY.md`: the four stakeholder one-pagers, the risk
  calculator, the defensibility pack
- **`[YOU]`** Run it on your own agency for 30 days. Your numbers become the case study.

**Gate** — 30 days live on your own pipeline. Edit rate, cost per lead, response time, and
escalation accuracy all recorded as *your* numbers.

---

## Phase 9 — Second client, then productise

Do not build multi-tenant abstractions before client two. Build for client two, then
generalise the difference. Most agentic products die of premature platform-building.

---

## Decisions I made for you (overrule any of these)

1. **The role: Inbound Revenue Ops.** Chosen over support, content, or research because it
   has a cost baseline you can point at, you can dogfood it on your own bidder pipeline,
   and it is hard enough that doing it safely *is* the product. If you'd rather it be a
   support or onboarding FTE, the architecture transfers with maybe a day of rework.
2. **The name "Naib."** Deputy with delegated authority. Rename in 30 seconds if you hate
   it — it appears in file names only, not in logic.
3. **Guardrails before agents (Phase 0).** Slower to first demo, dramatically faster to
   first paying client. This is the biggest structural bet in the plan.
4. **No autonomous sending in v1, no flag to enable it.** Graduated autonomy arrives in
   Phase 8 with clean-log thresholds attached.
5. **Postgres over a vector-DB service, Compose over Kubernetes.** Cost and explainability
   both favour boring infrastructure for this buyer.
6. **Roman Urdu support treated as core, not nice-to-have.** It is a real moat in your
   market against generic imported tooling.
7. **The dashboard is scoped as a reassurance surface, not an analytics product.**

## What only you can supply

- 40–60 labelled real inbound messages (Phase 2)
- The real playbook: services, scope templates, price bands, floor (Phase 1)
- Twenty proposal reviews in your own voice (Phase 4)
- Thirty days of dogfooding, which converts into every proof number you'll ever quote
