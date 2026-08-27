# Naib — for Security / the data owner

*One page, addressed to whoever reviews vendors before they touch inbound data. Fill in the
`{{ }}` placeholders per prospect. See docs/DEPLOYABILITY.md § 2 and § 3 — this page and the
red-team demo are the strongest move in the sales process, not an afterthought at the end.*

## What you're worried about

Untrusted text, client data, and exfiltration risk from a system that reads every inbound
message and has model-driven behavior in the loop.

## The untrusted-content architecture

Every inbound message (email, WhatsApp, form, voicemail transcript) is treated as
attacker-controlled data from the moment it arrives:

- It is wrapped in an explicit delimiter (`===UNTRUSTED-CONTENT===`) and never concatenated
  into an instruction string.
- The only agent that reads it (`IntakeAgent`) runs with a **read-only tool set** — it cannot
  send, write, or approve anything, by construction, not by prompt instruction.
- An input guardrail scans for injection patterns (delimiter-escape attempts, instruction-style
  language, price-manipulation phrasing — including Roman Urdu variants, not just English)
  *before* any agent sees the content, and trips a hard stop, not a soft warning.
- Downstream agents (qualification, proposal drafting) only ever see a schema-validated,
  structured `NormalizedLead` — never the raw text. The blast radius of a successful injection
  stops at that schema boundary.

## Permission tiers

- Nothing sends. `send_email`, `send_whatsapp`, `write_crm`, `commit_price` are all
  `needs_approval=True` in every configuration Naib ships — there is no flag that turns this
  off.
- A price floor output guardrail rejects any quote outside your configured floor before it can
  reach a human, let alone a client.
- Every tool call, guardrail outcome, model, token count, and decision is written to an
  append-only event log (`agent_events`) with an input hash — reconstructable, not a shrug, if
  you ever ask "why did it say that."

## The red-team suite, with its actual numbers

{{REDTEAM_CORPUS_SIZE}} adversarial cases — prompt injection, delimiter escapes, price
manipulation in English and Roman Urdu, jailbreak attempts — run against every change before it
ships. Current pass rate: **{{REDTEAM_PASS_RATE}}**. This isn't a claim; it's re-run on demand.

## Data residency, retention, deletion

- {{HOSTING_REGION — e.g. "Hosted on a VPS in your chosen region; Karachi/Pakistan hosting
  available as a stated option."}}
- {{RETENTION_POLICY — e.g. "Postgres backups retained 14 days, encrypted at rest."}}
- Raw inbound message text is **not stored** after processing — only a hash (for dedup) and the
  schema-validated extraction survive. There is less of your clients' data at rest than you'd
  expect from a system that reads every message.
- Deletion: {{DELETION_PROCESS}}

## See it fail safely, live

Ask for the demo where a real prompt-injection payload is sent through the actual intake
pipeline — you'll watch it get blocked, logged, and turned into an escalation, in real time.
