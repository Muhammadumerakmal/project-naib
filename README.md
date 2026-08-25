# Naib — Inbound Revenue Operations Digital FTE

> *Naib* (نائب): a deputy — one who acts on behalf of another, with delegated authority.
> Rename freely. The name is a placeholder you can overrule in 30 seconds.

**What it is:** not "an AI tool." A **hire**. Naib is a Digital FTE that owns the inbound
revenue desk for a small services business: it watches inbound channels, qualifies leads
against an ICP, enriches them, drafts scoped proposals from your playbook, runs follow-up
cadences, and escalates to a human the moment it is unsure.

**Why this role, of all roles** (judgment call — see "Decisions I made for you" in `PLAN.md`):

1. **It has a known cost baseline.** Every prospect already pays someone to do this, or
   loses deals because nobody does. That gives you a number to compare against — which is
   the entire foundation of the Deployability principle *"make risk the enemy."*
2. **You can dogfood it.** You already route every bidder lead through the agency before
   pricing. Run Naib on your own pipeline first. Ninety days later you own real numbers
   from a real business — which satisfies *"advocacy over promises"* without borrowing a
   single stat from a McKinsey deck.
3. **It is the highest-anxiety role to automate**, which makes it the best showcase for
   defensibility. Inbound email is attacker-controllable text. Proposals contain prices.
   Getting this safe is a harder engineering problem than a chatbot, and *that difficulty
   is the product.*

---

## Repo map

```
naib/
├── CLAUDE.md              # The constitution. Claude Code reads this every session.
├── PLAN.md                # 9 phases, executable one at a time via /phase
├── docs/
│   ├── ARCHITECTURE.md    # Agent topology, tools, guardrails, data model
│   ├── EVALS.md           # Eval harness, red-team suite, ship gates
│   └── DEPLOYABILITY.md   # The commercial layer — how this gets bought
└── .claude/
    ├── settings.json      # Hooks: lint/type/test on edit, secret + destructive blocks
    ├── agents/            # Subagents: architect, eval-writer, red-teamer, reviewer
    └── commands/          # /phase, /ship-check, /red-team, /brief
```

## How to start

```bash
# 1. Drop this kit into a fresh repo
git init naib && cd naib   # copy these files in

# 2. Bootstrap the Python project
uv init --python 3.12
uv add openai-agents fastapi uvicorn sqlmodel asyncpg pydantic-settings httpx
uv add --dev pytest pytest-asyncio ruff mypy

# 3. Open Claude Code and run the first phase
claude
> /phase 0
```

Do not skip Phase 0. It builds the guardrail scaffolding *before* the agents, which is the
inverse of how most agentic projects are built and the reason most of them never leave pilot.

---

## The working rhythm

This project runs on the **10-80-10 Rhythm Rule**:

| | Who | What |
|---|---|---|
| **10%** | You | Define the phase goal, confirm the brief, supply real data |
| **80%** | Claude Code | Research, architect, write, test, red-team, document |
| **10%** | You | Review, refine, add your voice, ship |

Anything in `PLAN.md` marked **`[YOU]`** is in your 10% and cannot be delegated —
usually because it requires access to real client conversations, real pricing, or a
judgment only the person who owns the business can make.
