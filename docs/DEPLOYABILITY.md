# Deployability

Your framework, applied to this specific product. The point of this file is that every
commercial claim traces back to a build artifact — nothing here is a slide you write later.

**Deployability** = the confidence a team feels that this will survive contact with their
actual business. AI pilots die of *no decision*, not competition. The demo works, everyone
nods, six months later it is still a pilot.

---

## 1. Make risk the enemy

They are not comparing Naib to a competitor. They are comparing it to **doing nothing**,
which has a known cost of zero and a familiar shape.

**Build artifact:** a risk calculator, populated during discovery, that makes doing nothing
expensive on paper.

```
Inbound enquiries / month            ___
Average time to first response       ___ hours
Enquiries that never got a reply     ___%     ← the number that hurts
Average deal value                   ___
Estimated leakage                    = enquiries × no-reply% × close-rate × deal value
Cost of a person doing this properly = ___/month
Naib cost                            = ___/month
```

Then remove the risk of *saying yes*: 30-day paid pilot, on their real inbound, fully
approval-gated, kill switch from day one, all data exportable, no lock-in. The pilot is not
a discount — it is risk transfer, and it should be priced as real work.

## 2. Reach beyond your champion

Your champion is the founder or Head of Ops. They will not be in the room when it dies.
Four other people can kill it, and three of them will never speak to you.

**Build artifact:** the proposal ships with four one-pagers, each addressed to someone who
never took your call.

| Who | What they actually fear | The page answers |
|---|---|---|
| **Finance** | A recurring bill that scales unpredictably | Fixed monthly + measured cost-per-lead from the eval suite. A ceiling, and the mechanism that enforces it. |
| **The person whose workflow it touches** | "Am I being replaced" | It drafts, you approve. Show the approval queue screenshot. Their job becomes reviewing 20 drafts instead of writing 20 emails. Say this plainly rather than dancing around it — the dancing is what they distrust. |
| **Security / data owner** | Untrusted text, client data, exfiltration | The untrusted-content architecture, the permission tiers, the red-team suite with its numbers, data residency, retention settings, deletion. |
| **The ops lead who gets blamed** | "It hallucinates and I own that" | Nothing sends without approval. Every decision has a record. Here is the kill switch. Here is the escalation policy. Here is what it does when unsure — it stops. |

Write these once, template them per client. The champion forwards them. That forwarding is
the actual sales motion.

## 3. Sell defensibility, not capability

*"I can explain this to my board if it fails"* beats *"it handles 40 tools."*

The evals, the logs, the approval ledger, the kill switch, the human-in-the-loop gates —
these are not risk mitigation you mention at the end. **They are the pitch.** The demo
should spend as much time on the trace viewer as on the happy path.

**The strongest demo move available to you:** open the red-team suite live, inject a
prompt-injection payload into a fake inbound email, and let them watch it get blocked, get
logged, and produce an escalation. Nobody else in your market is demoing that. Most cannot.

**Build artifact:** the Defensibility Pack, generated per prospect — architecture summary,
current eval report, sample trace export, incident runbook, kill-switch documentation.

## 4. Advocacy over promises

Every agency posts the same n8n screenshot. The differentiator is somebody else saying you
shipped.

**Build artifact:** dogfood first (Phase 8), then a case study from your own agency with
your own numbers — leads processed, response time before and after, edit rate trending
down, injections blocked. Then client one becomes a reference for client two, in writing,
with numbers, with their name on it if they will allow it.

Do not borrow statistics. A Bain number about enterprise buyers is not evidence about your
product. One real number from your own pipeline outperforms ten borrowed ones, because the
borrowed ones signal that you have none of your own.

## 5. Show buyers you're one of them

**Build artifacts, not talking points:**
- Roman Urdu and Urdu handling as a core feature — imported tooling fails at this
- Karachi / Pakistan hosting and data residency as a stated option
- Pricing in PKR with a USD option, sized for a 5–50 person services business
- Case studies from companies of the same size and shape, not enterprise logos
- A stack their existing developer recognises and could take over — which sounds like it
  weakens your position and in fact removes their largest objection

---

## Pricing shape **`[YOU]`**

A structure to react to, not a recommendation — you know this market and I do not:

- **Pilot:** fixed fee, 30 days, their real inbound, full approval gating, cancel anytime
- **Then:** monthly platform fee + metered per-lead cost above an included volume
- **Autonomy tiers** as an upsell that is genuinely earned: after 30 days of clean logs and
  an edit rate below threshold, specific actions unlock. Priced, but more importantly it
  gives the buyer a sense of *control over the pace* — which is the actual thing they are
  buying.

## The one-line positioning

> Naib is a Digital FTE for your inbound revenue desk. It reads every enquiry, qualifies it,
> drafts the proposal, and chases the follow-up — and it never sends anything without you.

The second clause is what sells it. Lead with it, don't apologise for it.
