# CLAUDE.md — Naib

Project constitution. Keep this short and true. If a rule here is being ignored, the fix is
usually a hook (enforce it) or a subagent (delegate it) — not more text in this file.

## What we are building

**Naib** — an Inbound Revenue Operations Digital FTE, sold as a product to small services
businesses. Python 3.12 + OpenAI Agents SDK + FastAPI + Postgres, React/Vite dashboard.

Read `PLAN.md` for the phase you are in. Read `docs/ARCHITECTURE.md` before writing any
agent, tool, or guardrail. Read `docs/EVALS.md` before writing any test.

## Commands

```bash
uv run pytest                      # tests
uv run pytest -m eval              # eval suite (slow, costs money)
uv run pytest -m redteam           # injection + jailbreak suite
uv run ruff check --fix .          # lint
uv run mypy src/                   # types
uv run uvicorn naib.api:app --reload
uv run python -m naib.cli replay <lead_id>   # re-score a lead's stored normalized data
uv run python -m naib.cli onboard ...        # onboard a new client (Phase 8)
uv run python -m naib.cli pack <client_id> --output-dir <dir>   # Defensibility Pack
```

## Non-negotiable rules

These exist because this product handles untrusted text and quotes prices. Violating them
is not a style error, it is a security or commercial incident.

1. **Untrusted content never gets tool authority.** Inbound email/WhatsApp/form text is
   attacker-controlled. It is *data*, always wrapped in a delimited block, never appended
   raw into instructions. Any agent that reads untrusted content runs with a read-only tool
   set. Escalate privileges only after a guardrail has cleared the content.
2. **No agent sends anything.** Agents draft. A human approves. `send_email`,
   `send_whatsapp`, `write_crm`, and `commit_price` are all `needs_approval=True`. There is
   no config flag that turns this off in v1. Autonomy is earned per-client, per-action,
   after 30 days of clean logs — and that is a Phase 8 feature, not a Phase 4 shortcut.
3. **Every decision is reconstructable.** Every run writes a structured event to the
   `agent_events` table: input hash, agent, tool calls, guardrail outcomes, model, tokens,
   cost, latency, and the final decision with its reason string. If a client asks "why did
   it say that," we answer with a record, not a shrug.
4. **Prices come from the playbook, never from the model.** The proposal agent selects a
   price *band* from a structured playbook table. It may not compute, interpolate, or
   invent a number. An output guardrail rejects any quote outside the configured floor.
5. **Structured outputs everywhere.** Every agent that feeds another agent returns a
   Pydantic model, not prose. Prose is only for the final human-facing artifact.
6. **Confidence is a first-class output.** Every classification carries a confidence and a
   reason. Below threshold → hand off to `EscalationAgent`. A confident wrong answer is
   worse than an escalation, because escalations are cheap and wrong answers cost trust.

## Code conventions

- `src/naib/` package layout. Agents in `agents/`, tools in `tools/`, guardrails in
  `guardrails/`, schemas in `schemas/`, storage in `store/`.
- Async by default. `Runner.run`, never `run_sync`, outside of tests and CLI.
- Full type annotations. `mypy` strict on `src/`. No `Any` without a `# why:` comment.
- Pydantic v2 models for all agent I/O. One model per file in `schemas/`.
- No secrets in code. `pydantic-settings` reads from env. Never read or print `.env`.
- Tests colocated in `tests/` mirroring `src/`. Mark eval tests `@pytest.mark.eval`.
- Conventional commits: `feat(agents): add qualifier handoff`.

## Agents SDK conventions

- **Handoff vs agent-as-tool is a deliberate choice, not a coin flip.** Handoff = ownership
  of the conversation transfers and does not return (intake → qualifier → proposal).
  Agent-as-tool = returns a value to the caller (enrichment, retrieval). If you are unsure,
  ask; do not guess. Document the choice in a comment.
- Guardrails: input guardrails only fire on the *first* agent in a run, output guardrails
  only on the agent producing final output. For per-call checks inside a multi-agent
  workflow, use **tool guardrails**. Choose accordingly — this trips people up constantly.
- Tripwires raise. Catch `InputGuardrailTripwireTriggered` at the API boundary and return a
  structured refusal + an escalation event. Never let a tripwire become a 500.
- Sessions are Postgres-backed and keyed per lead thread. Never in-memory in production.
- Tracing stays on. Set `workflow_name` per pipeline so traces are greppable.
- Model routing: cheap/fast model for intake + classification, strong model for proposal
  drafting and escalation briefs. Configure in `settings`, never hardcode a model string
  inside an agent definition.

## When to delegate

- Architecture or topology questions → `@agent-architect`
- Writing or extending the eval suite → `@eval-writer`
- Anything touching untrusted input or a new tool → `@injection-red-teamer`
- Before closing a phase → `@deployability-reviewer`

## Working rhythm (10-80-10)

Confirm the brief for the phase in one short paragraph, then build the whole phase without
stopping to ask permission for routine decisions. Make the call, note it in the handoff
summary, and let it be overruled. Do not hand back half-finished work with "let me know if
you want me to continue."

Ask before proceeding only when: the decision changes the commercial shape of the product,
requires real client data you do not have, or would violate a rule above.
