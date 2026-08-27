# Naib — for the Ops lead who gets blamed if it breaks

*One page, addressed to whoever owns the outcome if this goes wrong. Fill in the `{{ }}`
placeholders per prospect. See docs/DEPLOYABILITY.md § 2 — this person fears "it hallucinates
and I own that," and the page has to answer that directly.*

## What you're worried about

"It hallucinates and I own that."

## Nothing sends without you

Every draft — a proposal, a follow-up, a price — sits in an approval queue until a human
approves, edits, or rejects it. There is no configuration flag, no autonomy setting, no
"trusted client" exception that skips this in v1. If it's wrong, it's wrong in a draft nobody
outside your team has seen yet.

## Every decision has a record

Click any lead and open its trace: every agent that touched it, every tool call, every
guardrail outcome, the model used, the cost, the latency, and the final decision with its
reason — in plain language, not a raw log dump. If a client asks "why did it say that," you
answer with a record, signed (HMAC-SHA256) so it can't be quietly edited after the fact.

## Here is the kill switch

One button, on the dashboard, reachable by a non-technical person without asking anyone for
help. It halts every run for your account instantly — a queued job that hasn't started yet
simply never starts. {{KILL_SWITCH_TEST_NOTE — e.g. "Tested against the real job queue, not
just in isolation — see the Defensibility Pack."}}

## Here is what it does when it's not sure

It stops. Low confidence, an out-of-ICP request, conflicting budget signals, legal or
compliance language, or a message from an existing client — any of these route straight to a
human-readable escalation brief instead of a drafted reply. Escalations are cheap. A confident
wrong answer is the expensive failure mode, and the whole design optimizes against it.

## Autonomy is earned, never assumed

Nothing is autonomous in v1. Per-action autonomy (starting with the lowest-risk actions) only
becomes available to a specific client after **{{AUTONOMY_WINDOW_DAYS}} days of clean logs** —
zero edits, zero rejections — on that exact action, tracked and shown on your dashboard. You
watch the number climb before anything changes, and you can decline to enable it at all.

## The incident path

See `docs/INCIDENT_RUNBOOK.md` for what happens, in order, if something does go wrong —
written before you need it, not improvised during it.
