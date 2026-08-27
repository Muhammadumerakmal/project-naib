# Incident runbook

What to do, in order, when something goes wrong with a live Naib deployment. Written before
it's needed — see the ops-lead one-pager (`docs/one-pagers/ops-lead.md`), which points here.
Part of the Defensibility Pack (`docs/DEPLOYABILITY.md` § 3, built by
`naib.defensibility_pack`).

## 1. Stop it

Every incident starts here, before diagnosis. The dashboard's kill switch
(`POST /clients/{client_id}/kill-switch {"enabled": true}`, or the button on the dashboard) is
the fastest safe action available and never makes anything worse:

- A queued job that hasn't started yet **never starts** once the switch is on
  (`naib.worker._kill_switch_active`, checked at the top of every job entry point).
- It does not touch anything already sitting in the approval queue — those drafts are inert
  until a human decides, kill switch or not, so there is nothing time-sensitive to lose by
  stopping first and reading second.
- It does not abort a run that is already mid-execution. If a specific run is misbehaving
  right now, killing the queue stops the *next* one; the current run finishes on its own (it
  cannot send anything either way — see rule 2).

If unsure whether something is wrong: stop first, confirm second. There is no cost to a false
alarm here.

## 2. Confirm nothing was sent

Nothing autonomous exists in v1 (CLAUDE.md rule 2) — every `send_email`, `send_whatsapp`,
`write_crm`, and `commit_price` call is `needs_approval=True` with no override. This means the
worst-case blast radius of a bad run is a bad **draft**, sitting in the approval queue, not a
message a client received. Check the approval queue (`GET /clients/{client_id}/approvals`) for
anything that looks wrong and reject it before it's actioned.

## 3. Find out what happened

- Pull the trace for the affected lead: `GET /leads/{lead_id}/trace`. It's signed
  (HMAC-SHA256, `naib.trace_export.verify_trace`) — verify it before trusting it if you suspect
  tampering, not just data corruption.
- The trace shows every agent, tool call, guardrail outcome, model, cost, and the final
  decision with its reason, in order. Most incidents are explained by one line in this output.
- If the trace doesn't explain it, check `agent_events` directly for the `run_id` in question —
  the trace is a curated view, the table is the full one.

## 4. Common incident types and what they look like in the trace

| Symptom | Likely cause | Where to look |
|---|---|---|
| A draft quoted a price you didn't set | Should not be possible — the price-floor output guardrail rejects anything outside the configured floor before it's saved. If it happened anyway, this is a guardrail-bypass bug, escalate to engineering immediately with the trace attached. | `events[].guardrail == "price_floor"` should show `outcome: blocked` for any attempt; if it's missing entirely, that's the bug. |
| A draft claimed a capability you don't offer | The capability-claim output guardrail should have caught this. Same escalation path as above. | `events[].guardrail == "capability_claim"` |
| A lead that should have escalated didn't | Check `qualifications[].reasons` and the `escalate_below` threshold (`NAIB_ESCALATE_BELOW`) against the lead's actual confidence. | `trace.confidence`, `trace.escalations` |
| Suspiciously fluent or instruction-like text made it into a draft | Possible injection that slipped the guardrail — treat as a red-team gap, not a one-off. File it as a new case in `naib/data/redteam_corpus.json` once confirmed, so the eval suite catches the class going forward, not just this instance. | `events[].guardrail == "injection_scan"` |
| Cost spiked on one lead | Enrichment call budget (`NAIB_MAX_ENRICHMENT_CALLS`) may need lowering, or a retrieval loop is running longer than expected. | `events[].cost_usd`, `events[].tool` |

## 5. Fix, verify, resume

- Ship the fix, including a new red-team or golden-set case that would have caught it
  (`docs/EVALS.md`) — an incident that doesn't leave behind a regression test is one you agreed
  to have again.
- Run the full suite (`uv run pytest`) plus the relevant marked suite
  (`-m eval` / `-m redteam` / `-m budget`) before resuming.
- Turn the kill switch back off (i.e. re-enable processing) only after you can say what
  happened and what changed — not just that the immediate symptom stopped.

## 6. Tell the client

Every incident gets a plain-language note to the client: what happened, what it did and didn't
touch (see step 2 — usually "nothing sent"), what changed to prevent it, and a link to the
signed trace. This is not optional PR — it's the same "nothing to hide" posture the trace
viewer sells in the first place (`docs/DEPLOYABILITY.md` § 3).
